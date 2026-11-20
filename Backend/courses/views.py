from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from openpyxl import load_workbook

from accounts.permissions import IsAdminOrStaff, IsLecturer
from courses.models import Course, LecturerCourse, StudentCourse, Timetable, Subject, LecturerSubject, Classroom, Department

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
        course_id=course_id,
        id__in=LecturerSubject.objects.filter(
            lecturer=request.user
        ).values_list("subject_id", flat=True)
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


@api_view(["GET"])
@permission_classes([IsLecturer])
def lecturer_timetable(request):

    assigned_course_ids = LecturerCourse.objects.filter(
        lecturer=request.user
    ).values_list("course_id", flat=True)

    timetable = Timetable.objects.filter(
        lecturer=request.user,
        course_id__in=assigned_course_ids,
    ).select_related(
        "course",
        "subject",
        "lecturer",
    ).order_by(
        "day",
        "start_time",
    )

    return Response({
        "timetable": [
            {
                "id": item.id,
                "course": {
                    "id": item.course.id,
                    "name": item.course.name,
                    "code": item.course.code,
                },
                "subject": {
                    "id": item.subject.id,
                    "name": item.subject.name,
                    "code": item.subject.code,
                },
                "day": item.day,
                "day_name": item.get_day_display(),
                "start_time": item.start_time.strftime("%H:%M"),
                "end_time": item.end_time.strftime("%H:%M"),
                "room": item.room,
            }
            for item in timetable
        ]
    })



# ==========================================================
# ADMIN TIMETABLE MANAGEMENT - ALL DEPARTMENTS
# ==========================================================

def admin_timetable_data(item):
    return {
        "id": item.id,
        "department_id": item.course.department_id,
        "department": item.course.department.name,
        "course_id": item.course_id,
        "course": item.course.name,
        "course_code": item.course.code,
        "subject_id": item.subject_id,
        "subject": item.subject.name,
        "subject_code": item.subject.code,
        "lecturer_id": item.lecturer_id,
        "lecturer": item.lecturer.get_full_name() or item.lecturer.username,
        "day": item.day,
        "day_label": item.get_day_display(),
        "start_time": item.start_time.strftime("%H:%M"),
        "end_time": item.end_time.strftime("%H:%M"),
        "room": item.room,
    }


@api_view(["GET"])
@permission_classes([IsAdminOrStaff])
def admin_timetable_options(request):
    departments = Department.objects.all().order_by("name")
    courses = Course.objects.select_related("department").all().order_by("name")
    subjects = Subject.objects.select_related("course").all().order_by("name")
    lecturers = User.objects.filter(
        groups__name__iexact="Lecturer"
    ).distinct().order_by("username")

    return Response({
        "departments": [
            {"id": d.id, "name": d.name}
            for d in departments
        ],
        "courses": [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "department_id": c.department_id,
                "department": c.department.name,
            }
            for c in courses
        ],
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "course_id": s.course_id,
            }
            for s in subjects
        ],
        "lecturers": [
            {
                "id": lecturer.id,
                "name": lecturer.get_full_name() or lecturer.username,
                "username": lecturer.username,
            }
            for lecturer in lecturers
        ],
        "days": [
            {"value": value, "label": label}
            for value, label in Timetable.DAYS
        ],
    })


@api_view(["GET", "POST"])
@permission_classes([IsAdminOrStaff])
def admin_timetable_list(request):
    if request.method == "GET":
        timetable = Timetable.objects.select_related(
            "course__department",
            "subject",
            "lecturer",
        ).all().order_by("day", "start_time")

        department_id = request.query_params.get("department_id")
        course_id = request.query_params.get("course_id")
        day = request.query_params.get("day")

        if department_id:
            timetable = timetable.filter(course__department_id=department_id)
        if course_id:
            timetable = timetable.filter(course_id=course_id)
        if day:
            timetable = timetable.filter(day=day)

        return Response([
            admin_timetable_data(item) for item in timetable
        ])

    data = request.data

    course = Course.objects.filter(id=data.get("course_id")).select_related("department").first()
    subject = Subject.objects.filter(id=data.get("subject_id")).first()
    lecturer = User.objects.filter(
        id=data.get("lecturer_id"),
        groups__name__iexact="Lecturer",
    ).first()

    if not course or not subject or not lecturer:
        return Response(
            {"detail": "Select a valid course, subject and lecturer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if subject.course_id != course.id:
        return Response(
            {"detail": "The selected subject does not belong to the selected course."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    day = data.get("day")
    valid_days = [choice[0] for choice in Timetable.DAYS]
    if day not in valid_days:
        return Response(
            {"detail": "Select a valid day."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_time = data.get("start_time")
    end_time = data.get("end_time")

    if not start_time or not end_time or start_time >= end_time:
        return Response(
            {"detail": "End time must be later than start time."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    item = Timetable.objects.create(
        course=course,
        subject=subject,
        lecturer=lecturer,
        day=day,
        start_time=start_time,
        end_time=end_time,
        room=data.get("room", ""),
    )

    item = Timetable.objects.select_related(
        "course__department", "subject", "lecturer"
    ).get(id=item.id)

    return Response(
        admin_timetable_data(item),
        status=status.HTTP_201_CREATED,
    )


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsAdminOrStaff])
def admin_timetable_detail(request, pk):
    item = Timetable.objects.select_related(
        "course__department", "subject", "lecturer"
    ).filter(id=pk).first()

    if not item:
        return Response(
            {"detail": "Timetable entry not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        item.delete()
        return Response({"message": "Timetable entry deleted."})

    data = request.data
    course_id = data.get("course_id", item.course_id)
    subject_id = data.get("subject_id", item.subject_id)
    lecturer_id = data.get("lecturer_id", item.lecturer_id)

    course = Course.objects.filter(id=course_id).first()
    subject = Subject.objects.filter(id=subject_id).first()
    lecturer = User.objects.filter(
        id=lecturer_id,
        groups__name__iexact="Lecturer",
    ).first()

    if not course or not subject or not lecturer:
        return Response(
            {"detail": "Select a valid course, subject and lecturer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if subject.course_id != course.id:
        return Response(
            {"detail": "The selected subject does not belong to the selected course."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    day = data.get("day", item.day)
    if day not in [choice[0] for choice in Timetable.DAYS]:
        return Response(
            {"detail": "Select a valid day."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_time = data.get("start_time", item.start_time.strftime("%H:%M"))
    end_time = data.get("end_time", item.end_time.strftime("%H:%M"))

    if not start_time or not end_time or start_time >= end_time:
        return Response(
            {"detail": "End time must be later than start time."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    item.course = course
    item.subject = subject
    item.lecturer = lecturer
    item.day = day
    item.start_time = start_time
    item.end_time = end_time
    item.room = data.get("room", item.room)
    item.save()

    item = Timetable.objects.select_related(
        "course__department", "subject", "lecturer"
    ).get(id=item.id)

    return Response(admin_timetable_data(item))


# ==========================================================
# ADMIN ACADEMIC MANAGEMENT
# ==========================================================

@api_view(["GET"])
@permission_classes([IsAdminOrStaff])
def admin_academic_options(request):
    departments = Department.objects.all().order_by("name")
    courses = Course.objects.select_related("department").all().order_by("name")
    subjects = Subject.objects.select_related("course").all().order_by("name")
    classrooms = Classroom.objects.all().order_by("room_name")
    lecturers = User.objects.filter(
        groups__name__iexact="Lecturer"
    ).distinct().order_by("username")

    return Response({
        "departments": [
            {"id": d.id, "name": d.name} for d in departments
        ],
        "courses": [
            {
                "id": c.id,
                "name": c.name,
                "code": c.code,
                "department_id": c.department_id,
                "department": c.department.name,
            } for c in courses
        ],
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "course_id": s.course_id,
                "course": s.course.name,
            } for s in subjects
        ],
        "classrooms": [
            {
                "id": r.id,
                "room_name": r.room_name,
                "room_number": r.room_number,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "altitude": r.altitude,
                "radius_meters": r.radius_meters,
            } for r in classrooms
        ],
        "lecturers": [
            {
                "id": l.id,
                "name": l.get_full_name() or l.username,
                "username": l.username,
            } for l in lecturers
        ],
    })


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsAdminOrStaff])
def admin_course_detail(request, pk):
    course = Course.objects.filter(id=pk).first()

    if not course:
        return Response(
            {"detail": "Course not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        course.delete()
        return Response({"message": "Course deleted successfully."})

    name = request.data.get("name", course.name)
    code = request.data.get("code", course.code)
    department_id = request.data.get("department_id", course.department_id)

    department = Department.objects.filter(id=department_id).first()

    if not name or not code or not department:
        return Response(
            {"detail": "Course name, code and valid department are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Course.objects.filter(code=code).exclude(id=pk).exists():
        return Response(
            {"detail": "A course with this code already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    course.name = name
    course.code = code
    course.department = department
    course.save()

    return Response({
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "department_id": course.department_id,
        "department": department.name,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAdminOrStaff])
def admin_subject_list_create(request):
    if request.method == "GET":
        subjects = Subject.objects.select_related("course").all().order_by("name")
        return Response([
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "course_id": s.course_id,
                "course": s.course.name,
            } for s in subjects
        ])

    name = request.data.get("name")
    code = request.data.get("code")
    course = Course.objects.filter(
        id=request.data.get("course_id")
    ).first()

    if not name or not code or not course:
        return Response(
            {"detail": "Subject name, code and valid course are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject = Subject.objects.create(
        name=name,
        code=code,
        course=course,
    )

    return Response({
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "course_id": subject.course_id,
        "course": course.name,
    }, status=status.HTTP_201_CREATED)


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsAdminOrStaff])
def admin_subject_detail(request, pk):
    subject = Subject.objects.filter(id=pk).first()

    if not subject:
        return Response(
            {"detail": "Subject not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        subject.delete()
        return Response({"message": "Subject deleted successfully."})

    name = request.data.get("name", subject.name)
    code = request.data.get("code", subject.code)
    course_id = request.data.get("course_id", subject.course_id)
    course = Course.objects.filter(id=course_id).first()

    if not name or not code or not course:
        return Response(
            {"detail": "Subject name, code and valid course are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subject.name = name
    subject.code = code
    subject.course = course
    subject.save()

    return Response({
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "course_id": subject.course_id,
        "course": course.name,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAdminOrStaff])
def admin_classroom_list_create(request):
    if request.method == "GET":
        classrooms = Classroom.objects.all().order_by("room_name")
        return Response([
            {
                "id": r.id,
                "room_name": r.room_name,
                "room_number": r.room_number,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "altitude": r.altitude,
                "radius_meters": r.radius_meters,
            } for r in classrooms
        ])

    data = request.data
    room_name = data.get("room_name")
    room_number = data.get("room_number")
    radius = data.get("radius_meters", 20)

    if not room_name or not room_number:
        return Response(
            {"detail": "Room name and room number are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        radius = int(radius)
        if radius <= 0:
            raise ValueError
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        altitude = data.get("altitude")

        latitude = float(latitude) if latitude not in (None, "") else None
        longitude = float(longitude) if longitude not in (None, "") else None
        altitude = float(altitude) if altitude not in (None, "") else None

        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {"detail": "Enter valid GPS coordinates and a positive radius."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    classroom = Classroom.objects.create(
        room_name=room_name,
        room_number=room_number,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        radius_meters=radius,
    )

    return Response({
        "id": classroom.id,
        "room_name": classroom.room_name,
        "room_number": classroom.room_number,
        "latitude": classroom.latitude,
        "longitude": classroom.longitude,
        "altitude": classroom.altitude,
        "radius_meters": classroom.radius_meters,
    }, status=status.HTTP_201_CREATED)


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsAdminOrStaff])
def admin_classroom_detail(request, pk):
    classroom = Classroom.objects.filter(id=pk).first()

    if not classroom:
        return Response(
            {"detail": "Classroom not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "DELETE":
        classroom.delete()
        return Response({"message": "Classroom deleted successfully."})

    data = request.data

    room_name = data.get("room_name", classroom.room_name)
    room_number = data.get("room_number", classroom.room_number)

    try:
        radius = int(data.get("radius_meters", classroom.radius_meters))
        latitude_value = data.get("latitude", classroom.latitude)
        longitude_value = data.get("longitude", classroom.longitude)
        altitude_value = data.get("altitude", classroom.altitude)

        latitude = float(latitude_value) if latitude_value not in (None, "") else None
        longitude = float(longitude_value) if longitude_value not in (None, "") else None
        altitude = float(altitude_value) if altitude_value not in (None, "") else None

        if radius <= 0:
            raise ValueError
        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {"detail": "Enter valid GPS coordinates and a positive radius."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not room_name or not room_number:
        return Response(
            {"detail": "Room name and room number are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    classroom.room_name = room_name
    classroom.room_number = room_number
    classroom.latitude = latitude
    classroom.longitude = longitude
    classroom.altitude = altitude
    classroom.radius_meters = radius
    classroom.save()

    return Response({
        "id": classroom.id,
        "room_name": classroom.room_name,
        "room_number": classroom.room_number,
        "latitude": classroom.latitude,
        "longitude": classroom.longitude,
        "altitude": classroom.altitude,
        "radius_meters": classroom.radius_meters,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAdminOrStaff])
def admin_lecturer_assignments(request):
    if request.method == "GET":
        course_assignments = LecturerCourse.objects.select_related(
            "lecturer", "course"
        ).all()

        subject_assignments = LecturerSubject.objects.select_related(
            "lecturer", "subject", "subject__course"
        ).all()

        return Response({
            "course_assignments": [
                {
                    "id": a.id,
                    "lecturer_id": a.lecturer_id,
                    "lecturer": a.lecturer.get_full_name() or a.lecturer.username,
                    "course_id": a.course_id,
                    "course": a.course.name,
                } for a in course_assignments
            ],
            "subject_assignments": [
                {
                    "id": a.id,
                    "lecturer_id": a.lecturer_id,
                    "lecturer": a.lecturer.get_full_name() or a.lecturer.username,
                    "subject_id": a.subject_id,
                    "subject": a.subject.name,
                    "course_id": a.subject.course_id,
                    "course": a.subject.course.name,
                } for a in subject_assignments
            ],
        })

    assignment_type = request.data.get("type")
    lecturer = User.objects.filter(
        id=request.data.get("lecturer_id"),
        groups__name__iexact="Lecturer",
    ).first()

    if not lecturer:
        return Response(
            {"detail": "Select a valid lecturer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if assignment_type == "course":
        course = Course.objects.filter(
            id=request.data.get("course_id")
        ).first()

        if not course:
            return Response(
                {"detail": "Select a valid course."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, created = LecturerCourse.objects.get_or_create(
            lecturer=lecturer,
            course=course,
        )

    elif assignment_type == "subject":
        subject = Subject.objects.filter(
            id=request.data.get("subject_id")
        ).first()

        if not subject:
            return Response(
                {"detail": "Select a valid subject."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment, created = LecturerSubject.objects.get_or_create(
            lecturer=lecturer,
            subject=subject,
        )

    else:
        return Response(
            {"detail": "Assignment type must be course or subject."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"message": "Lecturer assignment saved.", "created": created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAdminOrStaff])
def admin_delete_lecturer_assignment(request, assignment_type, pk):
    if assignment_type == "course":
        assignment = LecturerCourse.objects.filter(id=pk).first()
    elif assignment_type == "subject":
        assignment = LecturerSubject.objects.filter(id=pk).first()
    else:
        return Response(
            {"detail": "Invalid assignment type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not assignment:
        return Response(
            {"detail": "Assignment not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    assignment.delete()
    return Response({"message": "Lecturer assignment removed."})
