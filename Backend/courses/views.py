from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

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
        lecturer_id=request.data["lecturer_id"],
        day=request.data["day"],
        start_time=request.data["start_time"],
        end_time=request.data["end_time"],
        room=request.data["room"],
    )
    return Response({"message": "Timetable created"}, status=201)
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