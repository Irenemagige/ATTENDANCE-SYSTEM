from django.urls import path

from datetime import datetime, timedelta


from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin
from academic_calendar.models import AcademicCalendarPeriod
from attendance.models import Attendance, AttendanceSession
from attendance.views import calculate_movement_attendance
from courses.models import Subject, Timetable
from students.models import Student

from .models import SemesterCalendar
from .serializers import SemesterCalendarSerializer



class SemesterCalendarListCreateView(generics.ListCreateAPIView):
    queryset = SemesterCalendar.objects.all()
    serializer_class = SemesterCalendarSerializer
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdmin])
def finalize_semester(request, calendar_id):
    try:
        calendar = SemesterCalendar.objects.get(id=calendar_id)
    except SemesterCalendar.DoesNotExist:
        return Response(
            {"error": "Semester calendar not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if calendar.is_finalized:
        return Response(
            {"message": "This semester has already been finalized."},
            status=status.HTTP_200_OK,
        )

    if not calendar.teaching_start_date or not calendar.teaching_end_date:
        return Response(
            {"error": "Set the teaching start and end dates first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if calendar.teaching_end_date < calendar.teaching_start_date:
        return Response(
            {"error": "The teaching end date cannot precede the start date."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    today = timezone.localdate()

    if today <= calendar.teaching_end_date:
        return Response(
            {
                "error": (
                    "The semester cannot be finalized until after "
                    "the teaching end date."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    sessions = AttendanceSession.objects.filter(
        date__gte=calendar.teaching_start_date,
        date__lte=calendar.teaching_end_date,
    )

    if sessions.filter(is_active=True).exists():
        return Response(
            {"error": "Some sessions are still active. Close them first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if sessions.filter(end_time__isnull=True).exists():
        return Response(
            {
                "error": (
                    "Some sessions have no recorded end time. "
                    "Review and close those sessions first."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()

    if sessions.filter(checkout_deadline__gt=now).exists():
        return Response(
            {
                "error": (
                    "Some checkout windows are still open. "
                    "Wait until the 10-minute checkout period has ended."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    unfinished_records = Attendance.objects.filter(
        session__in=sessions,
    ).filter(
        status="IN_PROGRESS"
    ) | Attendance.objects.filter(
        session__in=sessions,
        check_in_time__isnull=False,
        check_out_time__isnull=True,
    )

    if unfinished_records.exists():
        return Response(
            {
                "error": (
                    "Some attendance records are unfinished. "
                    "Allow the normal checkout finalization process to "
                    "complete, then try again."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    calendar.is_finalized = True
    calendar.finalized_at = now
    calendar.finalized_by = request.user
    calendar.save(
        update_fields=["is_finalized", "finalized_at", "finalized_by"]
    )

    return Response(
        {
            "message": "Semester finalized successfully.",
            "calendar_id": calendar.id,
            "is_finalized": calendar.is_finalized,
            "finalized_at": calendar.finalized_at,
        },
        status=status.HTTP_200_OK,
    )

def _student_semester_eligibility_for_student(student, calendar_id):

    try:
        calendar = SemesterCalendar.objects.get(id=calendar_id)
    except SemesterCalendar.DoesNotExist:
        return Response(
            {"error": "Semester calendar not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not calendar.teaching_start_date or not calendar.teaching_end_date:
        return Response(
            {
                "calendar_id": calendar.id,
                "semester_status": "Pending Review",
                "message": "Teaching dates have not been configured.",
                "subjects": [],
            },
            status=status.HTTP_200_OK,
        )

    start_date = calendar.teaching_start_date
    end_date = calendar.teaching_end_date
    today = timezone.localdate()
    effective_end = min(today, end_date)

    if today <= end_date:
        semester_status = "Monitoring"
    elif not calendar.is_finalized:
        semester_status = "Pending Review"
    else:
        semester_status = "Finalized"

    # Collect dates excluded from scheduled teaching.
    excluded_dates = set()

    periods = AcademicCalendarPeriod.objects.filter(calendar=calendar)

    for period in periods:
        if period.period_type not in {
            "BREAK", "REVISION", "EXAM", "OTHER"
        }:
            continue

        cursor = max(period.start_date, start_date)
        period_end = min(period.end_date, effective_end)

        while cursor <= period_end:
            excluded_dates.add(cursor)
            cursor += timedelta(days=1)

    subjects = Subject.objects.filter(
        course=student.course
    ).order_by("name")

    results = []

    for subject in subjects:
        timetables = list(
            Timetable.objects.filter(
                course=student.course,
                subject=subject,
            )
        )

        if not timetables:
            results.append({
                "subject_id": subject.id,
                "subject": subject.name,
                "subject_code": subject.code,
                "scheduled_hours": 0,
                "attended_hours": 0,
                "attendance_percentage": 0,
                "threshold_percentage": 75,
                "status": (
                    "Monitoring"
                    if semester_status == "Monitoring"
                    else "Pending Review"
                ),
                "message": "No timetable is configured for this subject.",
            })
            continue

        # Map weekday codes to timetable entries.
        timetable_by_day = {}

        for timetable in timetables:
            timetable_by_day.setdefault(
                timetable.day, []
            ).append(timetable)

        # Calculate the expected teaching hours and number of
        # scheduled class occurrences during the calendar period.
        scheduled_hours = 0.0
        expected_sessions_by_date = {}
        cursor = start_date

        while cursor <= effective_end:
            day_code = cursor.strftime("%a").upper()[:3]

            if cursor not in excluded_dates:
                daily_timetables = timetable_by_day.get(day_code, [])

                for timetable in daily_timetables:
                    start_dt = datetime.combine(
                        cursor, timetable.start_time
                    )
                    end_dt = datetime.combine(
                        cursor, timetable.end_time
                    )

                    duration = (
                        end_dt - start_dt
                    ).total_seconds() / 3600

                    if duration <= 0:
                        duration += 24

                    scheduled_hours += duration

                if daily_timetables:
                    expected_sessions_by_date[cursor] = len(
                        daily_timetables
                    )

            cursor += timedelta(days=1)

        sessions = list(
            AttendanceSession.objects.filter(
                course=student.course,
                subject=subject,
                date__gte=start_date,
                date__lte=effective_end,
            ).order_by("date", "id")
        )

        sessions_by_date = {}

        for session in sessions:
            if session.date not in excluded_dates:
                sessions_by_date[session.date] = (
                    sessions_by_date.get(session.date, 0) + 1
                )

        # Missing expected class sessions require review.
        needs_review = any(
            sessions_by_date.get(expected_date, 0) < expected_count
            for expected_date, expected_count
            in expected_sessions_by_date.items()
        )

        attended_hours = 0.0

        for session in sessions:
            if session.date in excluded_dates:
                continue

            # A session must be closed before it can be assessed.
            if session.is_active or not session.end_time:
                needs_review = True
                continue

            if (
                session.checkout_deadline
                and session.checkout_deadline > timezone.now()
            ):
                needs_review = True
                continue

            record = Attendance.objects.filter(
                student=student,
                session=session,
            ).first()

            # Missing student records must not silently count as zero.
            if record is None:
                needs_review = True
                continue

            if record.status == "IN_PROGRESS" or (
                record.check_in_time is not None
                and record.check_out_time is None
            ):
                needs_review = True
                continue

            if record.check_in_time is None:
                # A completed ABSENT record is a valid zero-attendance
                # result; it does not need movement logs.
                continue

            movement = calculate_movement_attendance(record)
            verified_seconds = max(
                0, movement["attended_seconds"]
            )

            # Correction 1: cap each record by that session's
            # actual duration, not the timetable's whole daily duration.
            actual_duration_seconds = max(
                0,
                (session.end_time - session.start_time).total_seconds(),
            )

            verified_seconds = min(
                verified_seconds,
                actual_duration_seconds,
            )

            attended_hours += verified_seconds / 3600

        # Never allow the total numerator to exceed the semester
        # timetable denominator.
        attended_hours = min(attended_hours, scheduled_hours)

        percentage = (
            round(attended_hours / scheduled_hours * 100, 2)
            if scheduled_hours > 0
            else 0
        )

        if semester_status == "Monitoring":
            subject_status = "Monitoring"
        elif not calendar.is_finalized or needs_review:
            subject_status = "Pending Review"
        elif scheduled_hours <= 0:
            subject_status = "Pending Review"
        else:
            subject_status = (
                "Eligible" if percentage >= 75 else "Not Eligible"
            )

        results.append({
            "subject_id": subject.id,
            "subject": subject.name,
            "subject_code": subject.code,
            "scheduled_hours": round(scheduled_hours, 2),
            "attended_hours": round(attended_hours, 2),
            "attendance_percentage": percentage,
            "threshold_percentage": 75,
            "status": subject_status,
        })

    return Response(
        {
            "student_id": student.id,
            "student_name": student.full_name,
            "course": student.course.name,
            "calendar_id": calendar.id,
            "academic_year": calendar.academic_year,
            "semester": calendar.semester,
            "semester_status": semester_status,
            "is_finalized": calendar.is_finalized,
            "finalized_at": calendar.finalized_at,
            "subjects": results,
        },
        status=status.HTTP_200_OK,
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def student_semester_eligibility(request, calendar_id):
    """Return eligibility for the currently authenticated student."""
    try:
        student = Student.objects.select_related(
            "user", "course"
        ).get(user=request.user)
    except Student.DoesNotExist:
        return Response(
            {"error": "Student profile not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return _student_semester_eligibility_for_student(
        student, calendar_id
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_semester_eligibility(request, calendar_id):
    """Return semester eligibility for all registered students."""
    try:
        calendar = SemesterCalendar.objects.get(id=calendar_id)
    except SemesterCalendar.DoesNotExist:
        return Response(
            {"error": "Semester calendar not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    students = Student.objects.select_related(
        "user", "course"
    ).order_by("full_name")

    student_results = []

    for student in students:
        result = _student_semester_eligibility_for_student(
            student, calendar_id
        )

        if result.status_code != status.HTTP_200_OK:
            return result

        student_data = dict(result.data)

        # Include student details even when calendar dates
        # have not yet been configured.
        student_data.setdefault("student_id", student.id)
        student_data.setdefault("student_name", student.full_name)
        student_data.setdefault(
            "course",
            student.course.name if student.course else None,
        )

        student_results.append(student_data)

    today = timezone.localdate()

    if not calendar.teaching_start_date or not calendar.teaching_end_date:
        semester_status = "Pending Review"
    elif today <= calendar.teaching_end_date:
        semester_status = "Monitoring"
    elif not calendar.is_finalized:
        semester_status = "Pending Review"
    else:
        semester_status = "Finalized"

    return Response(
        {
            "calendar_id": calendar.id,
            "academic_year": calendar.academic_year,
            "semester": calendar.semester,
            "semester_status": semester_status,
            "is_finalized": calendar.is_finalized,
            "finalized_at": calendar.finalized_at,
            "student_count": len(student_results),
            "students": student_results,
        },
        status=status.HTTP_200_OK,
    )
