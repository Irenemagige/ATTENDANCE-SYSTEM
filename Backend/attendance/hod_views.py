
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsHOD
from attendance.models import AttendanceSession, Attendance
from courses.models import HODDepartment


@api_view(["GET"])
@permission_classes([IsHOD])
def hod_dashboard(request):
    # 1. Find the department assigned to this HOD.
    assignment = HODDepartment.objects.filter(
        hod=request.user
    ).select_related("department").first()

    # 2. Deny access if this HOD has no department assignment.
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

    # 3. Restrict all dashboard data to this department.
    sessions = AttendanceSession.objects.filter(
        course__department=department
    )

    attendance = Attendance.objects.filter(
        session__course__department=department
    )

    # 4. Overview statistics.
    total_sessions = sessions.count()
    total_attendance = attendance.count()
    active_sessions = sessions.filter(is_active=True).count()

    # 5. Low-attendance alerts.
    low_attendance_alerts = []

    for session in sessions:
        session_attendance_count = Attendance.objects.filter(
            session=session
        ).count()

        if session_attendance_count < 5:
            low_attendance_alerts.append({
                "session_id": session.id,
                "course": session.course.name,
                "subject": session.subject.name,
                "total_attendance": session_attendance_count,
            })

    # 6. Sessions without recorded attendance.
    delay_analysis = []

    for session in sessions:
        first_attendance = Attendance.objects.filter(
            session=session
        ).order_by("check_in_time").first()

        if first_attendance is None:
            delay_analysis.append({
                "session_id": session.id,
                "course": session.course.name,
                "subject": session.subject.name,
                "issue": (
                    "No attendance recorded. This may indicate a delayed "
                    "session or a session with no attendance."
                ),
            })

    # 7. Course breakdown.
    courses_data = []

    courses = sessions.values(
        "course__id",
        "course__name",
    ).distinct()

    for course in courses:
        course_sessions = sessions.filter(
            course__id=course["course__id"]
        )

        course_attendance = attendance.filter(
            session__course__id=course["course__id"]
        )

        total = course_attendance.count()
        present = course_attendance.filter(status="PRESENT").count()

        percentage = (present / total * 100) if total else 0

        courses_data.append({
            "course": course["course__name"],
            "total_sessions": course_sessions.count(),
            "total_attendance": total,
            "present": present,
            "percentage": round(percentage, 2),
        })

    # 8. Return this department's dashboard.
    return Response({
        "department": department.name,
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_attendance": total_attendance,
        "low_attendance_alerts": low_attendance_alerts,
        "delay_analysis": delay_analysis,
        "courses": courses_data,
    })
