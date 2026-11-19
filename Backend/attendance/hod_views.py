
from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsHOD

from attendance.models import (
    AttendanceSession,
    Attendance,
    SessionChangeHistory,
)

from attendance.views import calculate_movement_attendance

from courses.models import (
    HODDepartment,
    Course,
    LecturerCourse,
    LecturerSubject,
    Timetable,
)

from students.models import Student


User = get_user_model()


def get_hod_department(user):
    """
    Return the department assigned to the authenticated HOD.
    """

    return (
        HODDepartment.objects
        .select_related("department")
        .filter(hod=user)
        .first()
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsHOD])
def hod_dashboard(request):
    """
    Department-scoped HOD dashboard.

    The HOD can view departmental information and attendance.
    This endpoint does not allow attendance or session modification.
    """

    assignment = get_hod_department(request.user)

    if assignment is None:
        return Response(
            {
                "detail": (
                    "No department has been assigned to this HOD account. "
                    "Please contact the administrator."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    department = assignment.department

    # --------------------------------------------------
    # 1. DEPARTMENT-SCOPED DATABASE QUERYSETS
    # --------------------------------------------------

    courses = Course.objects.filter(
        department=department
    )

    students = Student.objects.filter(
        course__department=department
    )

    sessions = AttendanceSession.objects.filter(
        course__department=department
    )

    attendance = Attendance.objects.filter(
        session__course__department=department
    )

    # --------------------------------------------------
    # 2. DEPARTMENT OVERVIEW STATISTICS
    # --------------------------------------------------

    total_courses = courses.count()

    total_subjects = sum(
        course.subjects.count()
        for course in courses
    )

    total_students = students.count()

    # Count lecturers with assignments or timetable entries
    # in this department, without counting the same lecturer twice.

    lecturer_ids = set(
        LecturerCourse.objects.filter(
            course__department=department
        ).values_list("lecturer_id", flat=True)
    )

    lecturer_ids.update(
        LecturerSubject.objects.filter(
            subject__course__department=department
        ).values_list("lecturer_id", flat=True)
    )

    lecturer_ids.update(
        Timetable.objects.filter(
            course__department=department
        ).values_list("lecturer_id", flat=True)
    )

    total_lecturers = len(lecturer_ids)

    total_sessions = sessions.count()

    active_sessions = sessions.filter(
        is_active=True
    )

    active_sessions_count = active_sessions.count()

    # Average individual session attendance percentage.
    # Invalid attempts and unfinished records are excluded.

    average_attendance = attendance.filter(
        status__in=[
            "PRESENT",
            "LATE",
            "PARTIAL_ATTENDANCE",
            "ABSENT",
        ]
    ).aggregate(
        average=Avg("attendance_percentage")
    )["average"]

    average_attendance = round(
        float(average_attendance or 0),
        2,
    )

    # --------------------------------------------------
    # 3. LIVE ATTENDANCE MONITORING
    # --------------------------------------------------

    live_sessions_data = []

    for session in active_sessions.select_related(
        "course",
        "subject",
        "classroom",
        "lecturer",
    ).order_by("-start_time"):

        enrolled_students = Student.objects.filter(
            course=session.course
        ).order_by("full_name")

        attendance_records = {
            record.student_id: record
            for record in Attendance.objects.filter(
                session=session
            ).select_related("student")
        }

        student_data = []

        checked_in_count = 0
        checked_out_count = 0
        not_checked_in_count = 0

        for student in enrolled_students:

            record = attendance_records.get(student.id)

            if record:

                checked_in = record.check_in_time is not None
                checked_out = record.check_out_time is not None

                if checked_in:
                    checked_in_count += 1

                if checked_out:
                    checked_out_count += 1

                # Use the existing verified movement calculation
                # for students who are currently checked in.

                if checked_in and not checked_out:

                    attendance_percentage = (
                        calculate_movement_attendance(record)[
                            "percentage"
                        ]
                    )

                else:

                    attendance_percentage = float(
                        record.attendance_percentage or 0
                    )

                student_status = record.status

                check_in = (
                    record.check_in_time.isoformat()
                    if record.check_in_time
                    else None
                )

                check_out = (
                    record.check_out_time.isoformat()
                    if record.check_out_time
                    else None
                )

            else:

                checked_in = False
                checked_out = False

                attendance_percentage = 0

                student_status = "NOT_CHECKED_IN"

                check_in = None
                check_out = None

            if not checked_in:
                not_checked_in_count += 1

            student_data.append({
                "student_id": student.id,
                "name": student.full_name,
                "registration": student.reg_number,
                "attendance_percentage": round(
                    min(
                        max(float(attendance_percentage), 0),
                        100,
                    ),
                    2,
                ),
                "status": student_status,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "check_in": check_in,
                "check_out": check_out,
            })

        live_sessions_data.append({

            "session_id": session.id,

            "course_id": session.course_id,
            "course": session.course.name,

            "subject_id": session.subject_id,
            "subject": session.subject.name,

            "lecturer_id": session.lecturer_id,
            "lecturer": (
                session.lecturer.get_full_name()
                or session.lecturer.username
            ),

            "date": (
                session.date.isoformat()
                if session.date
                else None
            ),

            "classroom": (
                session.classroom.room_name
                if session.classroom
                else None
            ),

            "room_number": (
                session.classroom.room_number
                if session.classroom
                else None
            ),

            "radius_meters": session.radius_meters,

            "start_time": (
                session.start_time.isoformat()
                if session.start_time
                else None
            ),

            "end_time": (
                session.end_time.isoformat()
                if session.end_time
                else None
            ),

            "is_override": session.is_override,
            "override_reason": session.override_reason,

            "total_students": len(student_data),
            "checked_in_count": checked_in_count,
            "checked_out_count": checked_out_count,
            "not_checked_in_count": not_checked_in_count,

            "students": student_data,
        })

    # --------------------------------------------------
    # 4. COURSE BREAKDOWN
    # Include every departmental course, even courses
    # that have not conducted attendance sessions.
    # --------------------------------------------------

    courses_data = []

    for course in courses.order_by("name"):

        course_sessions = sessions.filter(
            course=course
        )

        course_attendance = attendance.filter(
            session__course=course
        )

        course_average = course_attendance.filter(
            status__in=[
                "PRESENT",
                "LATE",
                "PARTIAL_ATTENDANCE",
                "ABSENT",
            ]
        ).aggregate(
            average=Avg("attendance_percentage")
        )["average"]

        courses_data.append({
            "course_id": course.id,
            "course": course.name,
            "course_code": course.code,
            "total_students": students.filter(
                course=course
            ).count(),
            "total_subjects": course.subjects.count(),
            "total_sessions": course_sessions.count(),
            "average_attendance": round(
                float(course_average or 0),
                2,
            ),
        })

    # --------------------------------------------------
    # 5. RECENT SESSION ACTIVITY
    # --------------------------------------------------

    recent_history = SessionChangeHistory.objects.filter(
        session__course__department=department
    ).select_related(
        "session",
        "session__course",
        "session__subject",
        "changed_by",
    ).order_by(
        "-recorded_at"
    )[:10]

    recent_activity_data = []

    for item in recent_history:

        recent_activity_data.append({
            "history_id": item.id,
            "session_id": item.session_id,
            "course": item.session.course.name,
            "subject": item.session.subject.name,
            "action": item.get_change_type_display(),
            "changed_by": (
                item.changed_by.get_full_name()
                or item.changed_by.username
                if item.changed_by
                else None
            ),
            "reason": item.reason,
            "recorded_at": item.recorded_at.isoformat(),
        })

    # --------------------------------------------------
    # 6. RETURN DEPARTMENT DASHBOARD DATA
    # --------------------------------------------------

    return Response({

        "department": {
            "id": department.id,
            "name": department.name,
        },

        "overview": {
            "total_students": total_students,
            "total_courses": total_courses,
            "total_subjects": total_subjects,
            "total_lecturers": total_lecturers,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions_count,
            "average_attendance": average_attendance,
        },

        "live_sessions": live_sessions_data,

        "courses": courses_data,

        "recent_activity": recent_activity_data,

        "last_updated": timezone.now().isoformat(),

    }, status=status.HTTP_200_OK)
