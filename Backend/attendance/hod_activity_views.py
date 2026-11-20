from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsHOD
from attendance.models import AttendanceSession, SessionChangeHistory
from attendance.hod_views import get_hod_department
from courses.models import Timetable
from academic_calendar.models import SemesterCalendar, AcademicCalendarPeriod


def _user_display(user):
    if not user:
        return "Unknown"
    return user.get_full_name().strip() or user.username


def _time_value(value):
    return value.isoformat() if value else None


def _build_lecturer_accountability(department):
    today = timezone.localdate()

    calendar = (
        SemesterCalendar.objects
        .filter(
            teaching_start_date__isnull=False,
            teaching_end_date__isnull=False,
        )
        .order_by("-uploaded_at")
        .first()
    )

    empty_result = {
        "calendar": None,
        "summary": {
            "lecturers": 0,
            "expected_classes": 0,
            "sessions_started": 0,
            "started_late": 0,
            "needs_review": 0,
        },
        "lecturers": [],
        "warning": "",
    }

    if not calendar:
        empty_result["warning"] = (
            "No semester calendar with valid teaching dates has been uploaded."
        )
        return empty_result

    teaching_start = calendar.teaching_start_date
    teaching_end = min(calendar.teaching_end_date, today)

    calendar_info = {
        "title": calendar.title,
        "academic_year": calendar.academic_year,
        "semester": calendar.get_semester_display(),
        "teaching_start_date": teaching_start.isoformat(),
        "teaching_end_date": calendar.teaching_end_date.isoformat(),
    }

    if teaching_end < teaching_start:
        empty_result["calendar"] = calendar_info
        empty_result["warning"] = (
            "The teaching period has not started yet."
        )
        return empty_result

    excluded_periods = list(
        AcademicCalendarPeriod.objects
        .filter(
            calendar=calendar,
            start_date__lte=teaching_end,
            end_date__gte=teaching_start,
        )
        .values("start_date", "end_date", "name", "period_type")
    )

    excluded_dates = set()

    for period in excluded_periods:
        current = max(period["start_date"], teaching_start)
        last = min(period["end_date"], teaching_end)

        while current <= last:
            excluded_dates.add(current)
            current += timedelta(days=1)

    timetable_entries = list(
        Timetable.objects
        .filter(course__department=department)
        .select_related("lecturer", "course", "subject")
        .order_by("lecturer__username", "day", "start_time")
    )

    if not timetable_entries:
        empty_result["calendar"] = calendar_info
        empty_result["warning"] = (
            "No timetable entries were found for this department."
        )
        return empty_result

    timetable_ids = [entry.id for entry in timetable_entries]

    actual_sessions = (
        AttendanceSession.objects
        .filter(
            course__department=department,
            timetable_id__in=timetable_ids,
            date__gte=teaching_start,
            date__lte=teaching_end,
        )
        .select_related(
            "lecturer",
            "course",
            "subject",
            "classroom",
            "timetable",
        )
        .order_by("start_time")
    )

    sessions_by_slot = {}

    for session in actual_sessions:
        key = (session.timetable_id, session.date)
        sessions_by_slot.setdefault(key, []).append(session)

    weekday_codes = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    current_date = teaching_start

    lecturer_data = {}

    while current_date <= teaching_end:
        if current_date not in excluded_dates:
            weekday_code = weekday_codes[current_date.weekday()]

            for timetable in timetable_entries:
                if timetable.day != weekday_code:
                    continue

                lecturer_id = timetable.lecturer_id

                if lecturer_id not in lecturer_data:
                    lecturer_data[lecturer_id] = {
                        "lecturer_id": lecturer_id,
                        "lecturer": _user_display(timetable.lecturer),
                        "expected_classes": 0,
                        "sessions_started": 0,
                        "started_late": 0,
                        "needs_review": 0,
                        "on_time": 0,
                        "classes": [],
                    }

                lecturer = lecturer_data[lecturer_id]
                lecturer["expected_classes"] += 1

                matching_sessions = sessions_by_slot.get(
                    (timetable.id, current_date), []
                )

                scheduled_start = timezone.make_aware(
                    datetime.combine(current_date, timetable.start_time),
                    timezone.get_current_timezone(),
                )

                if not matching_sessions:
                    lecturer["needs_review"] += 1

                    lecturer["classes"].append({
                        "date": current_date.isoformat(),
                        "course": str(timetable.course),
                        "subject": str(timetable.subject),
                        "classroom": timetable.room or "Not specified",
                        "scheduled_start": timetable.start_time.isoformat(),
                        "scheduled_end": timetable.end_time.isoformat(),
                        "actual_start": None,
                        "delay_minutes": None,
                        "session_id": None,
                        "status": "NEEDS_REVIEW",
                        "details": (
                            "No attendance session was found for this "
                            "scheduled class."
                        ),
                    })
                    continue

                session = matching_sessions[0]
                actual_start = session.start_time

                if timezone.is_naive(actual_start):
                    actual_start = timezone.make_aware(
                        actual_start,
                        timezone.get_current_timezone(),
                    )

                delay_seconds = (
                    actual_start - scheduled_start
                ).total_seconds()

                delay_minutes = max(0, int(delay_seconds / 60))

                lecturer["sessions_started"] += 1

                if delay_seconds > 0:
                    lecturer["started_late"] += 1
                    class_status = "STARTED_LATE"
                    details = (
                        f"Session started {delay_minutes} minute(s) "
                        "after the scheduled time."
                    )
                else:
                    lecturer["on_time"] += 1
                    class_status = "ON_TIME"
                    details = "Session started on time."

                classroom = session.classroom

                lecturer["classes"].append({
                    "date": current_date.isoformat(),
                    "course": str(timetable.course),
                    "subject": str(timetable.subject),
                    "classroom": (
                        classroom.room_name if classroom
                        else timetable.room or "Not specified"
                    ),
                    "scheduled_start": timetable.start_time.isoformat(),
                    "scheduled_end": timetable.end_time.isoformat(),
                    "actual_start": _time_value(session.start_time),
                    "delay_minutes": delay_minutes,
                    "session_id": session.id,
                    "status": class_status,
                    "is_override": session.is_override,
                    "details": details,
                })

        current_date += timedelta(days=1)

    lecturers = list(lecturer_data.values())

    for lecturer in lecturers:
        lecturer["classes"].sort(
            key=lambda item: (item["date"], item["scheduled_start"]),
            reverse=True,
        )

        lecturer["status"] = (
            "NEEDS_REVIEW"
            if lecturer["needs_review"] > 0
            else "ON_TRACK"
        )

    lecturers.sort(
        key=lambda item: (
            -item["needs_review"],
            -item["started_late"],
            item["lecturer"].lower(),
        )
    )

    summary = {
        "lecturers": len(lecturers),
        "expected_classes": sum(
            item["expected_classes"] for item in lecturers
        ),
        "sessions_started": sum(
            item["sessions_started"] for item in lecturers
        ),
        "started_late": sum(
            item["started_late"] for item in lecturers
        ),
        "needs_review": sum(
            item["needs_review"] for item in lecturers
        ),
    }

    return {
        "calendar": calendar_info,
        "summary": summary,
        "lecturers": lecturers,
        "warning": (
            "Classes marked Needs Review may have been cancelled or "
            "rescheduled. The current system does not record approved "
            "cancellations or timetable changes."
        ),
    }


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
        .prefetch_related("attendance_set__student")
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

        for attendance in session.attendance_set.all():
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

    accountability = _build_lecturer_accountability(department)

    return Response({
        "department": department.name,
        "audit_records": audit_records,
        "history_records": history_records,
        "accountability": accountability,
        "last_updated": timezone.now().isoformat(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsHOD])
def hod_department_timetable(request):
    hod_profile = get_hod_department(request.user)

    if not hod_profile or not hod_profile.department:
        return Response(
            {"detail": "No department is assigned to this HOD account."},
            status=status.HTTP_404_NOT_FOUND,
        )

    department = hod_profile.department

    timetable = (
        Timetable.objects
        .filter(course__department=department)
        .select_related("course", "subject", "lecturer")
        .order_by("day", "start_time", "course__name")
    )

    return Response({
        "department": {
            "id": department.id,
            "name": department.name,
        },
        "total_entries": timetable.count(),
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
                "lecturer": _user_display(item.lecturer),
                "lecturer_id": item.lecturer_id,
                "day": item.day,
                "day_name": item.get_day_display(),
                "start_time": item.start_time.strftime("%H:%M"),
                "end_time": item.end_time.strftime("%H:%M"),
                "room": item.room,
            }
            for item in timetable
        ],
    })
