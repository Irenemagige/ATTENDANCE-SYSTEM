from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from openpyxl import load_workbook

from accounts.permissions import IsAdminOrStaff
from courses.models import Course, LecturerCourse, StudentCourse, Timetable, Subject,LecturerSubject,Classroom

User = get_user_model()

@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def assign_student_to_course(request):
    student_id = request.data.get("student_id")
    course_id = request.data.get("course_id")

    student = User.objects.filter(id=student_id, groups__name__iexact="Student").first()
    if not student:
        return Response({"detail": "Student user not found."}, status=status.HTTP_404_NOT_FOUND)

    course = Course.objects.filter(id=course_id).first()
    if not course:
        return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

    StudentCourse.objects.get_or_create(student=student, course=course)
    return Response({"message": "Student assigned successfully"})


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def assign_lecturer_to_course(request):
    lecturer_id = request.data.get("lecturer_id")
    course_id = request.data.get("course_id")

    lecturer = User.objects.filter(id=lecturer_id, groups__name__iexact="Lecturer").first()
    if not lecturer:
        return Response({"detail": "Lecturer user not found."}, status=status.HTTP_404_NOT_FOUND)

    course = Course.objects.filter(id=course_id).first()
    if not course:
        return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

    LecturerCourse.objects.get_or_create(lecturer=lecturer, course=course)
    return Response({"message": "Lecturer assigned successfully"})


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def create_timetable(request):
    Timetable.objects.create(
        course_id=request.data["course_id"],
        subject_id=request.data["subject_id"],
        lecturer_id=request.data["lecturer_id"],
        day=request.data["day"],
        start_time=request.data["start_time"],
        end_time=request.data["end_time"],
        room=request.data.get("room", ""),
    )

    return Response(
        {"message": "Timetable created"},
        status=status.HTTP_201_CREATED,
    )
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lecturer_courses(request):
    course_ids = LecturerCourse.objects.filter(
        lecturer=request.user
    ).values_list("course_id", flat=True)

    courses = Course.objects.filter(
        id__in=course_ids
    )

    return Response([
        {
            "id": course.id,
            "name": course.name,
            "code": course.code,
        }
        for course in courses
    ])
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_list(request):
    courses = Course.objects.select_related("department").all()

    return Response([
        {
            "id": course.id,
            "name": course.name,
            "code": course.code,
            "department": course.department.name,
        }
        for course in courses
    ])


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def course_create(request):
    course = Course.objects.create(
        name=request.data.get("name"),
        code=request.data.get("code"),
        department_id=request.data.get("department_id"),
    )

    return Response(
        {
            "message": "Course created",
            "id": course.id
        },
        status=201
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subject_list(request):
    course_id = request.query_params.get("course_id")

    if not course_id:
        return Response(
            {"detail": "course_id is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Make sure the lecturer is assigned to this course
    lecturer_course = LecturerCourse.objects.filter(
        lecturer=request.user,
        course_id=course_id
    ).first()

    if not lecturer_course:
        return Response(
            {"detail": "You are not assigned to this course."},
            status=status.HTTP_403_FORBIDDEN
        )

    subjects = Subject.objects.filter(
        course_id=course_id
    )

    return Response([
        {
            "id": subject.id,
            "name": subject.name,
            "code": subject.code,
            "course_id": subject.course_id,
        }
        for subject in subjects
    ])
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def classroom_list(request):
    classrooms = Classroom.objects.all()

    return Response([
        {
            "id": classroom.id,
            "room_name": classroom.room_name,
            "room_number": classroom.room_number,
            "latitude": classroom.latitude,
            "longitude": classroom.longitude,
            "altitude": classroom.altitude,
            "radius_meters": classroom.radius_meters,
        }
        for classroom in classrooms
    ])
    
@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def upload_timetable_excel(request):
    excel_file = request.FILES.get("file")

    if not excel_file:
        return Response(
            {"error": "Please upload an Excel file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        workbook = load_workbook(excel_file, data_only=True)
    except Exception:
        return Response(
            {"error": "The uploaded file is not a valid Excel file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    created_count = 0
    errors = []

    day_map = {
        "Monday": "MON",
        "Tuesday": "TUE",
        "Wednesday": "WED",
        "Thursday": "THU",
        "Friday": "FRI",
        "Saturday": "SAT",
        "Sunday": "SUN",
    }

    for sheet in workbook.worksheets:

        # Expected sheet name = course name
        course_name = sheet.title.strip()

        try:
            course = Course.objects.get(name__iexact=course_name)
        except Course.DoesNotExist:
            errors.append(
                f"Sheet '{course_name}': Course not found."
            )
            continue

        # Row 1 = title
        # Row 2 = Time / Monday / Tuesday / ...
        header_row = 1

        headers = {}

        for column in range(1, sheet.max_column + 1):
            value = sheet.cell(
                row=header_row,
                column=column,
            ).value

            if value:
                headers[column] = str(value).strip()

        if "Time" not in headers.values():
            errors.append(
                f"Sheet '{course_name}': Missing 'Time' column."
            )
            continue

        time_column = next(
            column
            for column, value in headers.items()
            if value == "Time"
        )

        for row in range(header_row + 1, sheet.max_row + 1):

            time_value = sheet.cell(
                row=row,
                column=time_column,
            ).value

            if not time_value:
                continue

            time_text = str(time_value).strip()

            if "-" not in time_text:
                errors.append(
                    f"{course_name}, row {row}: Invalid time '{time_text}'."
                )
                continue

            start_text, end_text = [
                value.strip()
                for value in time_text.split("-", 1)
            ]

            try:
                from datetime import datetime

                start_time = datetime.strptime(
                    start_text,
                    "%H:%M",
                ).time()

                end_time = datetime.strptime(
                    end_text,
                    "%H:%M",
                ).time()

            except ValueError:
                errors.append(
                    f"{course_name}, row {row}: "
                    f"Invalid time range '{time_text}'."
                )
                continue

            if start_time >= end_time:
                errors.append(
                    f"{course_name}, row {row}: "
                    f"Start time must be before end time."
                )
                continue

            for column, day_name in headers.items():

                if day_name == "Time":
                    continue

                if day_name not in day_map:
                    continue

                cell_value = sheet.cell(
                    row=row,
                    column=column,
                ).value

                if not cell_value:
                    continue

                cell_text = str(cell_value).strip()

                lines = [
                    line.strip()
                    for line in cell_text.splitlines()
                    if line.strip()
                ]

                if len(lines) < 2:
                    errors.append(
                        f"{course_name}, {day_name}, "
                        f"{time_text}: "
                        f"Cell must contain Subject on the first line "
                        f"and Lecturer on the second line."
                    )
                    continue

                subject_name = lines[0]

                if subject_name.strip().lower() == "clouds and devops":
                   subject_name = "Cloud and Devops"

                lecturer_name = lines[1]

                if lecturer_name.startswith("(Lecturer ") and lecturer_name.endswith(")"):
                   lecturer_name = lecturer_name[len("(Lecturer "):-1].strip()

                

                if lecturer_name.startswith("(Lecturer ") and lecturer_name.endswith(")"):
                    lecturer_name = lecturer_name[len("(Lecturer "):-1].strip()

                # Find subject belonging to this course
                try:
                    subject = Subject.objects.get(
                        course=course,
                        name__iexact=subject_name,
                    )
                except Subject.DoesNotExist:
                    errors.append(
                        f"{course_name}, {day_name}, {time_text}: "
                        f"Subject '{subject_name}' was not found "
                        f"under this course."
                    )
                    continue

                # Find lecturer
                lecturer = User.objects.filter(
                    first_name__iexact=lecturer_name
                ).first()

                if not lecturer:
                    lecturer = User.objects.filter(
                        username__iexact=lecturer_name
                    ).first()

                if not lecturer:
                    errors.append(
                        f"{course_name}, {day_name}, {time_text}: "
                        f"Lecturer '{lecturer_name}' was not found."
                    )
                    continue

                # Verify lecturer is assigned to the course
                if not LecturerCourse.objects.filter(
                    lecturer=lecturer,
                    course=course,
                ).exists():
                    errors.append(
                        f"{course_name}, {day_name}, {time_text}: "
                        f"{lecturer_name} is not assigned to "
                        f"{course_name}."
                    )
                    continue

                # Verify lecturer is assigned to the subject
                if not LecturerSubject.objects.filter(
                    lecturer=lecturer,
                    subject=subject,
                ).exists():
                    errors.append(
                        f"{course_name}, {day_name}, {time_text}: "
                        f"{lecturer_name} is not assigned to "
                        f"{subject_name}."
                    )
                    continue

                # Prevent duplicate timetable records
                if Timetable.objects.filter(
                    course=course,
                    subject=subject,
                    lecturer=lecturer,
                    day=day_map[day_name],
                    start_time=start_time,
                    end_time=end_time,
                ).exists():
                    continue

                Timetable.objects.create(
                    course=course,
                    subject=subject,
                    lecturer=lecturer,
                    day=day_map[day_name],
                    start_time=start_time,
                    end_time=end_time,
                    room="",
                )

                created_count += 1

    return Response(
        {
            "message": "Timetable Excel processed.",
            "created": created_count,
            "errors": errors,
        },
        status=status.HTTP_201_CREATED if created_count else status.HTTP_400_BAD_REQUEST,
    )
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_timetable(request):
    student_course = StudentCourse.objects.filter(
        student=request.user
    ).select_related("course").first()

    if not student_course:
        return Response(
            {"detail": "You are not enrolled in a course."},
            status=status.HTTP_404_NOT_FOUND,
        )

    course = student_course.course

    timetable = Timetable.objects.filter(
        course=course
    ).select_related(
        "course",
        "subject",
        "lecturer",
    ).order_by(
        "day",
        "start_time",
    )

    return Response(
        {
            "course": {
                "id": course.id,
                "name": course.name,
                "code": course.code,
            },
            "timetable": [
                {
                    "id": item.id,
                    "day": item.day,
                    "start_time": item.start_time.strftime("%H:%M"),
                    "end_time": item.end_time.strftime("%H:%M"),
                    "subject": {
                        "id": item.subject.id,
                        "name": item.subject.name,
                        "code": item.subject.code,
                    },
                    "lecturer": {
                        "id": item.lecturer.id,
                        "name": (
                            item.lecturer.get_full_name()
                            or item.lecturer.username
                        ),
                    },
                    "room": item.room,
                }
                for item in timetable
            ],
        }
    )