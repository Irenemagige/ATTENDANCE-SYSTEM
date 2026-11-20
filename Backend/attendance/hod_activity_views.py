from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsHOD
from attendance.models import AttendanceSession, Attendance, SessionChangeHistory
from attendance.hod_views import get_hod_department


def _user_display(user):
    if not user:
        return "Unknown"
    return user.get_full_name().strip() or user.username


def _time_value(value):
    return value.isoformat() if value else None


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsHOD])
def hod_audit_history(request):
    hod_assignment = get_hod_department(request.user)

    if not hod_assignment:
        return Response(
            {"detail": "No department is assigned to this HOD."},
            status=status.HTTP_403_FORBIDDEN,
        )

    department = hod_assignment.department

    events = (
        SessionChangeHistory.objects
        .filter(session__course__department=department)
        .select_related(
            "changed_by",
            "session",
            "session__lecturer",
            "session__course",
            "session__subject",
            "session__classroom",
        )
        .order_by("-recorded_at")
    )

    audit_records = []

    for event in events:
        session = event.session
        classroom = session.classroom

        audit_records.append({
            "id": event.id,
            "session_id": session.id,
            "lecturer": _user_display(session.lecturer),
            "actor": _user_display(event.changed_by),
            "action": event.get_change_type_display(),
            "change_type": event.change_type,
            "reason": event.reason or "",
            "recorded_at": _time_value(event.recorded_at),
            "course": str(session.course),
            "subject": str(session.subject),
            "classroom": (
                classroom.room_name if classroom else "Not specified"
            ),
            "scheduled_start_time": _time_value(event.scheduled_start_time),
            "scheduled_end_time": _time_value(event.scheduled_end_time),
            "actual_start_time": _time_value(event.actual_start_time),
            "actual_end_time": _time_value(event.actual_end_time),
            "is_override": session.is_override,
        })

    completed_sessions = (
        AttendanceSession.objects
        .filter(
            course__department=department,
            ended_at__isnull=False,
        )
        .select_related(
            "lecturer",
            "course",
            "subject",
            "classroom",
        )
        .prefetch_related("attendance_records__student")
        .order_by("-start_time")
    )

    history_records = []

    for session in completed_sessions:
        classroom = session.classroom
        ended_at = session.ended_at

        duration_minutes = None
        if ended_at and session.start_time:
            duration_minutes = max(
                0,
                int((ended_at - session.start_time).total_seconds() / 60),
            )

        student_records = []

        for attendance in session.attendance_records.all():
            student = attendance.student

            student_records.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "registration": student.reg_number,
                "check_in": _time_value(attendance.check_in_time),
                "check_out": _time_value(attendance.check_out_time),
                "status": attendance.status,
                "attendance_percentage": float(
                    attendance.attendance_percentage or 0
                ),
            })

        history_records.append({
            "id": session.id,
            "date": session.date.isoformat() if session.date else None,
            "lecturer": _user_display(session.lecturer),
            "course": str(session.course),
            "subject": str(session.subject),
            "classroom": (
                classroom.room_name if classroom else "Not specified"
            ),
            "started_at": _time_value(session.start_time),
            "ended_at": _time_value(ended_at),
            "duration_minutes": duration_minutes,
            "is_override": session.is_override,
            "override_reason": session.override_reason or "",
            "students": student_records,
        })

    return Response({
        "department": department.name,
        "audit_records": audit_records,
        "history_records": history_records,
        "last_updated": timezone.now().isoformat(),
    })
