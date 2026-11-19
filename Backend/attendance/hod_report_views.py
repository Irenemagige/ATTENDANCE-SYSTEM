from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsHOD
from academic_calendar.models import SemesterCalendar, AcademicCalendarPeriod
from attendance.models import AttendanceSession, Attendance
from attendance.hod_views import get_hod_department, _hod_get_scheduled_hours, _hod_get_attended_hours
from courses.models import Course
from students.models import Student


FINAL_STATUSES = ["PRESENT", "LATE", "PARTIAL_ATTENDANCE", "ABSENT"]


def _name(user):
    if not user:
        return "Not available"

    return (
        user.get_full_name()
        or getattr(user, "username", "")
        or str(user)
    )


def _session_status(attendance):
    return getattr(attendance, "status", "UNKNOWN")


def _attendance_percentage(attendance):
    try:
        return float(attendance.attendance_percentage or 0)
    except (TypeError, ValueError):
        return 0.0


def _matches_search(search, *values):
    if not search:
        return True

    search = search.lower()
    return any(search in str(value or "").lower() for value in values)


def _build_report_rows(report_type, department, sessions, search):
    session_ids = [session.id for session in sessions]

    attendance_records = Attendance.objects.filter(
        session_id__in=session_ids,
        status__in=FINAL_STATUSES
    ).select_related(
        "student",
        "student__user",
        "student__course",
        "session",
        "session__course",
        "session__subject",
        "session__lecturer",
        "session__classroom",
    )

    records_by_student = defaultdict(list)
    records_by_session = defaultdict(list)

    for record in attendance_records:
        records_by_student[record.student_id].append(record)
        records_by_session[record.session_id].append(record)

    rows = []

    if report_type == "students":
        columns = [
            "Student",
            "Registration Number",
            "Course",
            "Year of Study",
            "Sessions Attended",
            "Late Sessions",
            "Partial Sessions",
            "Absent Sessions",
            "Attendance Percentage",
            "Last Attendance",
        ]

        students = Student.objects.filter(
            course__department=department
        ).select_related("user", "course").order_by("full_name")

        for student in students:
            records = records_by_student.get(student.id, [])

            if not records:
                continue

            scheduled_hours = 0.0
            attended_hours = 0.0

            for record in records:
                scheduled_hours += _hod_get_scheduled_hours(record.session)
                attended_hours += _hod_get_attended_hours(record)

            percentage = (
                attended_hours / scheduled_hours * 100
                if scheduled_hours > 0 else 0
            )

            attended_count = sum(
                1 for record in records
                if _session_status(record) in ["PRESENT", "LATE", "PARTIAL_ATTENDANCE"]
            )

            late_count = sum(
                1 for record in records
                if _session_status(record) == "LATE"
            )

            partial_count = sum(
                1 for record in records
                if _session_status(record) == "PARTIAL_ATTENDANCE"
            )

            absent_count = sum(
                1 for record in records
                if _session_status(record) == "ABSENT"
            )

            last_attendance = max(
                (record.check_in_time for record in records if record.check_in_time),
                default=None
            )

            student_name = student.full_name or _name(student.user)
            course_name = student.course.name if student.course else "Not assigned"

            if not _matches_search(
                search,
                student_name,
                student.reg_number,
                course_name,
                student.year_of_study,
            ):
                continue

            rows.append({
                "Student": student_name,
                "Registration Number": student.reg_number,
                "Course": course_name,
                "Year of Study": student.year_of_study,
                "Sessions Attended": attended_count,
                "Late Sessions": late_count,
                "Partial Sessions": partial_count,
                "Absent Sessions": absent_count,
                "Attendance Percentage": round(percentage, 2),
                "Last Attendance": (
                    timezone.localtime(last_attendance).strftime("%Y-%m-%d %H:%M")
                    if last_attendance else "No attendance"
                ),
            })

        return columns, rows

    if report_type == "courses":
        columns = [
            "Course",
            "Subject",
            "Sessions Held",
            "Registered Students Attending",
            "Present",
            "Late",
            "Partial",
            "Absent",
            "Average Attendance Percentage",
        ]

        grouped = defaultdict(list)

        for session in sessions:
            grouped[(session.course_id, session.subject_id)].append(session)

        for (course_id, subject_id), subject_sessions in grouped.items():
            first_session = subject_sessions[0]
            course_name = first_session.course.name if first_session.course else "Not available"
            subject_name = first_session.subject.name if first_session.subject else "Not available"

            subject_records = [
                record
                for session in subject_sessions
                for record in records_by_session.get(session.id, [])
            ]

            if not _matches_search(search, course_name, subject_name):
                continue

            percentages = [_attendance_percentage(record) for record in subject_records]

            rows.append({
                "Course": course_name,
                "Subject": subject_name,
                "Sessions Held": len(subject_sessions),
                "Registered Students Attending": len(set(
                    record.student_id for record in subject_records
                )),
                "Present": sum(1 for record in subject_records if _session_status(record) == "PRESENT"),
                "Late": sum(1 for record in subject_records if _session_status(record) == "LATE"),
                "Partial": sum(1 for record in subject_records if _session_status(record) == "PARTIAL_ATTENDANCE"),
                "Absent": sum(1 for record in subject_records if _session_status(record) == "ABSENT"),
                "Average Attendance Percentage": (
                    round(sum(percentages) / len(percentages), 2)
                    if percentages else 0
                ),
            })

        return columns, rows

    if report_type == "absenteeism":
        columns = [
            "Student",
            "Registration Number",
            "Course",
            "Subject",
            "Session Date",
            "Lecturer",
            "Attendance Status",
            "Attendance Percentage",
        ]

        for record in attendance_records:
            if _session_status(record) != "ABSENT":
                continue

            student = record.student
            session = record.session
            student_name = student.full_name or _name(student.user)
            course_name = session.course.name if session.course else "Not available"
            subject_name = session.subject.name if session.subject else "Not available"
            lecturer_name = _name(session.lecturer)

            if not _matches_search(
                search,
                student_name,
                student.reg_number,
                course_name,
                subject_name,
                lecturer_name,
            ):
                continue

            rows.append({
                "Student": student_name,
                "Registration Number": student.reg_number,
                "Course": course_name,
                "Subject": subject_name,
                "Session Date": str(session.date),
                "Lecturer": lecturer_name,
                "Attendance Status": "Absent",
                "Attendance Percentage": _attendance_percentage(record),
            })

        return columns, rows

    if report_type == "lecturers":
        columns = [
            "Lecturer",
            "Course",
            "Subject",
            "Classroom",
            "Session Date",
            "Scheduled Hours",
            "Students Recorded",
            "Present",
            "Late",
            "Partial",
            "Absent",
            "Session Attendance Percentage",
            "Session Status",
        ]

        for session in sessions:
            records = records_by_session.get(session.id, [])

            lecturer_name = _name(session.lecturer)
            course_name = session.course.name if session.course else "Not available"
            subject_name = session.subject.name if session.subject else "Not available"
            classroom_name = (
                session.classroom.room_name
                if session.classroom else "Not assigned"
            )

            if not _matches_search(
                search,
                lecturer_name,
                course_name,
                subject_name,
                classroom_name,
            ):
                continue

            present = sum(1 for record in records if _session_status(record) == "PRESENT")
            late = sum(1 for record in records if _session_status(record) == "LATE")
            partial = sum(1 for record in records if _session_status(record) == "PARTIAL_ATTENDANCE")
            absent = sum(1 for record in records if _session_status(record) == "ABSENT")

            total = len(records)
            attended = present + late + partial
            session_percentage = attended / total * 100 if total else 0

            if getattr(session, "auto_closed", False):
                session_status = "Auto-closed"
            elif getattr(session, "ended_at", None):
                session_status = "Ended"
            else:
                session_status = "Completed"

            rows.append({
                "Lecturer": lecturer_name,
                "Course": course_name,
                "Subject": subject_name,
                "Classroom": classroom_name,
                "Session Date": str(session.date),
                "Scheduled Hours": round(_hod_get_scheduled_hours(session), 2),
                "Students Recorded": total,
                "Present": present,
                "Late": late,
                "Partial": partial,
                "Absent": absent,
                "Session Attendance Percentage": round(session_percentage, 2),
                "Session Status": session_status,
            })

        return columns, rows

    return [], []


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsHOD])
def hod_reports(request):
    hod_assignment = get_hod_department(request.user)
    department = hod_assignment.department if hod_assignment else None

    if not department:
        return Response(
            {"detail": "No department is assigned to this HOD account."},
            status=status.HTTP_403_FORBIDDEN
        )

    report_type = request.query_params.get("report_type", "students").strip().lower()
    search = request.query_params.get("search", "").strip()

    allowed_types = ["students", "courses", "absenteeism", "lecturers"]

    if report_type not in allowed_types:
        return Response(
            {"detail": "Invalid report type.", "allowed_types": allowed_types},
            status=status.HTTP_400_BAD_REQUEST
        )

    academic_year = request.query_params.get("academic_year")
    semester = request.query_params.get("semester")

    calendar_query = SemesterCalendar.objects.all()

    if academic_year:
        calendar_query = calendar_query.filter(academic_year=academic_year)

    if semester:
        calendar_query = calendar_query.filter(semester=semester)

    calendar = calendar_query.first()

    if not calendar:
        return Response(
            {"detail": "No academic calendar was found for the selected academic year and semester."},
            status=status.HTTP_404_NOT_FOUND
        )

    if not calendar.teaching_start_date or not calendar.teaching_end_date:
        return Response(
            {"detail": "The selected academic calendar has no teaching date range."},
            status=status.HTTP_400_BAD_REQUEST
        )

    excluded_periods = AcademicCalendarPeriod.objects.filter(
        calendar=calendar,
        period_type__in=["BREAK", "REVISION", "EXAM", "OTHER"]
    )

    excluded_dates = []
    for period in excluded_periods:
        current_date = period.start_date
        while current_date <= period.end_date:
            excluded_dates.append(current_date)
            current_date += timezone.timedelta(days=1)

    sessions = AttendanceSession.objects.filter(
        course__department=department,
        date__gte=calendar.teaching_start_date,
        date__lte=calendar.teaching_end_date,
        is_active=False,
    ).filter(
        Q(end_time__isnull=False) | Q(ended_at__isnull=False)
    ).exclude(
        date__in=excluded_dates
    ).select_related(
        "course",
        "subject",
        "lecturer",
        "classroom",
    ).order_by("-date", "-start_time")

    session_list = list(sessions)

    columns, rows = _build_report_rows(
        report_type,
        department,
        session_list,
        search,
    )

    return Response({
        "department": department.name,
        "report_type": report_type,
        "academic_year": calendar.academic_year,
        "semester": calendar.semester,
        "columns": columns,
        "rows": rows,
        "total_records": len(rows),
        "generated_at": timezone.localtime().isoformat(),
    })

