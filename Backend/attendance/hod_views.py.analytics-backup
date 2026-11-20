
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Q
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsHOD

from academic_calendar.models import SemesterCalendar

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



# ==================================================
# HOD CUMULATIVE SUBJECT ATTENDANCE HELPERS
# These follow the lecturer attendance-history logic.
# ==================================================

def _hod_get_scheduled_hours(session):

    if session.is_override:
        return max(
            (session.override_duration_minutes or 0) / 60,
            0,
        )

    if session.timetable:
        start = session.timetable.start_time
        end = session.timetable.end_time

        if start and end:
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute

            if end_minutes <= start_minutes:
                end_minutes += 24 * 60

            return max(
                (end_minutes - start_minutes) / 60,
                0,
            )

    if session.start_time and session.end_time:
        return max(
            (
                session.end_time - session.start_time
            ).total_seconds() / 3600,
            0,
        )

    return 0


def _hod_get_attended_hours(attendance):

    if not attendance or not attendance.check_in_time:
        return 0

    result = calculate_movement_attendance(attendance)

    return max(
        result["attended_seconds"] / 3600,
        0,
    )


def _hod_calculate_student_subject_percentage(
    student,
    subject,
    current_session,
):

    records = Attendance.objects.filter(
        student=student,
        session__course=student.course,
        session__subject=subject,
        session__date__lte=current_session.date,
    ).filter(
        Q(
            check_in_time__isnull=False,
            check_out_time__isnull=False,
        )
        | Q(
            check_in_time__isnull=True,
            session__is_active=False,
        )
    ).select_related(
        "session",
        "session__timetable",
    )

    def legacy_percentage():

        total_scheduled = 0
        total_attended = 0

        for record in records:
            scheduled = _hod_get_scheduled_hours(record.session)
            attended = _hod_get_attended_hours(record)

            total_scheduled += scheduled
            total_attended += min(attended, scheduled)

        if total_scheduled <= 0:
            return 0

        return round(
            min(
                total_attended / total_scheduled * 100,
                100,
            ),
            2,
        )

    calendar = SemesterCalendar.objects.filter(
        teaching_start_date__isnull=False,
        teaching_end_date__isnull=False,
        teaching_start_date__lte=current_session.date,
        teaching_end_date__gte=current_session.date,
    ).first()

    if not calendar:
        return legacy_percentage()

    end_date = min(
        current_session.date,
        calendar.teaching_end_date,
    )

    excluded_dates = set()

    excluded_period_types = {
        "BREAK",
        "REVISION",
        "EXAM",
        "OTHER",
    }

    for period in calendar.periods.filter(
        period_type__in=excluded_period_types,
    ):
        period_date = max(
            period.start_date,
            calendar.teaching_start_date,
        )

        period_end = min(
            period.end_date,
            calendar.teaching_end_date,
        )

        while period_date <= period_end:
            excluded_dates.add(period_date)
            period_date += timedelta(days=1)

    timetables = Timetable.objects.filter(
        course=student.course,
        subject=subject,
    )

    if not timetables.exists():
        return legacy_percentage()

    total_scheduled_hours = 0
    total_attended_hours = 0

    scheduled_date = calendar.teaching_start_date

    while scheduled_date <= end_date:

        if scheduled_date not in excluded_dates:

            day_code = scheduled_date.strftime("%a").upper()[:3]

            for timetable in timetables:

                if timetable.day != day_code:
                    continue

                start = timetable.start_time
                end = timetable.end_time

                if not start or not end:
                    continue

                start_minutes = start.hour * 60 + start.minute
                end_minutes = end.hour * 60 + end.minute

                if end_minutes <= start_minutes:
                    end_minutes += 24 * 60

                total_scheduled_hours += (
                    end_minutes - start_minutes
                ) / 60

        scheduled_date += timedelta(days=1)

    for record in records:

        session_date = record.session.date

        if not session_date:
            continue

        if not (
            calendar.teaching_start_date
            <= session_date
            <= end_date
        ):
            continue

        if session_date in excluded_dates:
            continue

        scheduled = _hod_get_scheduled_hours(record.session)
        attended = _hod_get_attended_hours(record)

        total_attended_hours += min(
            attended,
            scheduled,
        )

    if total_scheduled_hours <= 0:
        return legacy_percentage()

    return round(
        min(
            total_attended_hours / total_scheduled_hours * 100,
            100,
        ),
        2,
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
    # --------------------------------------------------
    # 3. DEPARTMENT ATTENTION
    # Count unique students using cumulative subject
    # attendance percentages.
    # --------------------------------------------------

    students_requiring_attention_ids = set()
    critical_attendance_student_ids = set()

    for course in courses.order_by("name"):

        course_students = list(
            students.filter(
                course=course
            ).order_by("full_name")
        )

        for subject in course.subjects.all():

            # Find the latest finalized session for this
            # course and subject, across all lecturers.

            latest_finalized_record = Attendance.objects.filter(
                student__course=course,
                session__course=course,
                session__subject=subject,
            ).filter(
                Q(
                    check_in_time__isnull=False,
                    check_out_time__isnull=False,
                )
                | Q(
                    check_in_time__isnull=True,
                    session__is_active=False,
                )
            ).select_related(
                "session",
            ).order_by(
                "-session__date",
                "-session__start_time",
            ).first()

            # Do not flag students for subjects that
            # have no finalized attendance sessions.

            if not latest_finalized_record:
                continue

            latest_session = latest_finalized_record.session

            for student in course_students:

                subject_percentage = (
                    _hod_calculate_student_subject_percentage(
                        student,
                        subject,
                        latest_session,
                    )
                )

                if subject_percentage < 80:
                    students_requiring_attention_ids.add(
                        student.id
                    )

                if subject_percentage < 75:
                    critical_attendance_student_ids.add(
                        student.id
                    )

    students_requiring_attention = len(
        students_requiring_attention_ids
    )

    critical_attendance_cases = len(
        critical_attendance_student_ids
    )
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

        "department_attention": {
            "students_requiring_attention": students_requiring_attention,
            "critical_attendance_cases": critical_attendance_cases,
        },

        "live_sessions": live_sessions_data,

        "courses": courses_data,

        "recent_activity": recent_activity_data,

        "last_updated": timezone.now().isoformat(),

    }, status=status.HTTP_200_OK)




# ==================================================
# HOD DEPARTMENT STUDENT DIRECTORY
# Read-only, restricted to the authenticated HOD's department.
# ==================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated, IsHOD])
def hod_students(request):
    assignment = get_hod_department(request.user)

    if assignment is None:
        return Response(
            {"detail": "No department has been assigned to this HOD account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    department = assignment.department

    students = (
        Student.objects
        .filter(course__department=department)
        .select_related("user", "course", "course__department")
        .order_by("full_name")
    )

    student_data = []

    for student in students:
        records = Attendance.objects.filter(
            student=student,
            session__course__department=department,
        )

        total_records = records.count()

        attended_records = records.filter(
            status__in=[
                "PRESENT",
                "LATE",
                "PARTIAL_ATTENDANCE",
            ]
        ).count()

        absent_records = records.filter(status="ABSENT").count()

        latest_record = records.exclude(
            check_in_time__isnull=True
        ).order_by("-check_in_time").first()

        student_data.append({
            "student_id": student.id,
            "name": student.full_name,
            "registration": student.reg_number,
            "email": student.email,
            "phone_number": student.phone_number,
            "course_id": student.course_id,
            "course": student.course.name,
            "course_code": student.course.code,
            "year_of_study": student.year_of_study,
            "total_attendance_records": total_records,
            "attended_records": attended_records,
            "absent_records": absent_records,
            "last_attendance": (
                latest_record.check_in_time.isoformat()
                if latest_record else None
            ),
            "attendance_assessment": (
                "RECORDED" if total_records > 0 else "NO_RECORDS"
            ),
        })

    return Response({
        "department": {
            "id": department.id,
            "name": department.name,
        },
        "total_students": len(student_data),
        "students": student_data,
        "last_updated": timezone.now().isoformat(),
    }, status=status.HTTP_200_OK)
