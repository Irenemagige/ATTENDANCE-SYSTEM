from datetime import date
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Avg
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin
from academic_calendar.models import SemesterCalendar, AcademicCalendarPeriod
from courses.models import (
    Department, Course, Subject, Classroom, Timetable,
    LecturerCourse, LecturerSubject,
)
from students.models import Student
from .models import Attendance, AttendanceSession, MovementLog, SessionChangeHistory


User = get_user_model()


def _text(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _filters(request):
    return {
        "academic_year": request.query_params.get("academic_year", "").strip(),
        "semester": request.query_params.get("semester", "").strip(),
        "department": request.query_params.get("department", "").strip(),
        "course": request.query_params.get("course", "").strip(),
        "subject": request.query_params.get("subject", "").strip(),
        "lecturer": request.query_params.get("lecturer", "").strip(),
        "student_id": request.query_params.get("student_id", "").strip(),
        "session_id": request.query_params.get("session_id", "").strip(),
        "start_date": request.query_params.get("start_date", "").strip(),
        "end_date": request.query_params.get("end_date", "").strip(),
    }


def _sessions_for(filters):
    qs = AttendanceSession.objects.select_related(
        "course", "subject", "lecturer", "classroom"
    ).all()

    if filters["academic_year"]:
        qs = qs.filter(date__year=filters["academic_year"][:4])
    if filters["semester"]:
        calendars = SemesterCalendar.objects.filter(
            semester=filters["semester"]
        )
        if filters["academic_year"]:
            calendars = calendars.filter(academic_year=filters["academic_year"])
        date_ranges = [
            (c.teaching_start_date, c.teaching_end_date)
            for c in calendars
            if c.teaching_start_date and c.teaching_end_date
        ]
        if date_ranges:
            date_query = Q()
            for start, end in date_ranges:
                date_query |= Q(date__range=(start, end))
            qs = qs.filter(date_query)
        else:
            qs = qs.none()
    if filters["department"]:
        qs = qs.filter(course__department_id=filters["department"])
    if filters["course"]:
        qs = qs.filter(course_id=filters["course"])
    if filters["subject"]:
        qs = qs.filter(subject_id=filters["subject"])
    if filters["lecturer"]:
        qs = qs.filter(lecturer_id=filters["lecturer"])
    if filters["start_date"]:
        qs = qs.filter(date__gte=filters["start_date"])
    if filters["end_date"]:
        qs = qs.filter(date__lte=filters["end_date"])
    if filters["session_id"]:
        qs = qs.filter(id=filters["session_id"])
    return qs.order_by("-date", "-start_time")


def _students_for(filters):
    qs = Student.objects.select_related("user", "course", "course__department")
    if filters["department"]:
        qs = qs.filter(course__department_id=filters["department"])
    if filters["course"]:
        qs = qs.filter(course_id=filters["course"])
    if filters["student_id"]:
        qs = qs.filter(id=filters["student_id"])
    return qs.order_by("full_name")


def _attendance_rows(filters, report_type):
    from .views import calculate_movement_attendance

    sessions = _sessions_for(filters)
    records = Attendance.objects.select_related(
        "student", "student__course", "student__course__department",
        "session", "session__course", "session__subject",
        "session__lecturer",
    ).filter(session__in=sessions)

    if filters["student_id"]:
        records = records.filter(student_id=filters["student_id"])

    if report_type == "absent-students":
        records = records.filter(status="ABSENT")
    elif report_type == "late-arrivals":
        records = records.filter(status="LATE")
    elif report_type == "partial-attendance":
        records = records.filter(status="PARTIAL_ATTENDANCE")

    rows = []
    for record in records.order_by("-session__date", "student__full_name"):
        movement = calculate_movement_attendance(record)
        percentage = (
            movement.get("percentage", 0)
            if record.check_in_time and record.session.end_time
            else float(record.attendance_percentage or 0)
        )
        rows.append({
            "student": record.student.full_name,
            "registration_number": record.student.reg_number,
            "department": record.student.course.department.name if record.student.course and record.student.course.department else "",
            "course": record.student.course.name if record.student.course else "",
            "subject": record.session.subject.name if record.session.subject else "",
            "lecturer": record.session.lecturer.get_full_name() or record.session.lecturer.username,
            "session_id": record.session_id,
            "session_date": _text(record.session.date),
            "check_in": _text(record.check_in_time),
            "check_out": _text(record.check_out_time),
            "status": record.status,
            "attendance_percentage": round(float(percentage or 0), 2),
        })
    return rows


def _eligibility_rows(filters, report_type):
    from academic_calendar.views import _student_semester_eligibility_for_student

    calendars = SemesterCalendar.objects.all().order_by("-uploaded_at", "-id")
    if filters["academic_year"]:
        calendars = calendars.filter(academic_year=filters["academic_year"])
    if filters["semester"]:
        calendars = calendars.filter(semester=filters["semester"])

    calendar = calendars.first()
    if not calendar:
        return [], "No matching semester calendar was found. Upload or select a semester calendar first."

    rows = []
    for student in _students_for(filters):
        result = _student_semester_eligibility_for_student(student, calendar.id)
        if result.status_code != 200:
            continue

        for subject in result.data.get("subjects", []):
            status_value = subject.get("status", "Pending Review")
            if report_type == "eligible-students" and status_value != "Eligible":
                continue
            if report_type == "not-eligible-students" and status_value != "Not Eligible":
                continue

            rows.append({
                "student": student.full_name,
                "registration_number": student.reg_number,
                "department": student.course.department.name if student.course and student.course.department else "",
                "course": student.course.name if student.course else "",
                "subject": subject.get("subject", ""),
                "subject_code": subject.get("subject_code", ""),
                "scheduled_hours": subject.get("scheduled_hours", 0),
                "attended_hours": subject.get("attended_hours", 0),
                "attendance_percentage": subject.get("attendance_percentage", 0),
                "threshold_percentage": subject.get("threshold_percentage", 75),
                "eligibility_status": status_value,
                "semester_status": result.data.get("semester_status", ""),
                "academic_year": calendar.academic_year,
                "semester": calendar.semester,
            })

    if report_type == "eligibility-summary":
        grouped = {}
        for row in rows:
            key = (row["department"], row["course"], row["subject"])
            item = grouped.setdefault(key, {
                "department": key[0],
                "course": key[1],
                "subject": key[2],
                "eligible": 0,
                "not_eligible": 0,
                "pending_review": 0,
                "monitoring": 0,
                "total_students": 0,
            })
            item["total_students"] += 1
            status_value = row["eligibility_status"].lower().replace(" ", "_")
            if status_value in item:
                item[status_value] += 1
        rows = list(grouped.values())

    return rows, ""


def _build_report(request):
    report_type = request.query_params.get("report_type", "institution-attendance")
    filters = _filters(request)
    rows = []
    message = ""

    attendance_types = {
        "institution-attendance", "session-attendance", "student-attendance",
        "absent-students", "late-arrivals", "partial-attendance",
    }
    eligibility_types = {
        "eligible-students", "not-eligible-students", "eligibility-summary",
    }

    if report_type in attendance_types:
        rows = _attendance_rows(filters, report_type)

    elif report_type in eligibility_types:
        rows, message = _eligibility_rows(filters, report_type)

    elif report_type in {"students", "all-users"}:
        students = _students_for(filters)
        for student in students:
            rows.append({
                "full_name": student.full_name,
                "registration_number": student.reg_number,
                "email": student.email,
                "phone_number": student.phone_number,
                "department": student.course.department.name if student.course and student.course.department else "",
                "course": student.course.name if student.course else "",
                "year_of_study": student.year_of_study,
                "username": student.user.username,
                "role": "Student",
                "is_active": student.user.is_active,
            })
        if report_type == "all-users":
            student_user_ids = set(Student.objects.values_list("user_id", flat=True))
            users = User.objects.exclude(id__in=student_user_ids).prefetch_related("groups")
            for user in users:
                groups = ", ".join(user.groups.values_list("name", flat=True))
                rows.append({
                    "full_name": user.get_full_name(),
                    "registration_number": "",
                    "email": user.email,
                    "phone_number": "",
                    "department": "",
                    "course": "",
                    "year_of_study": "",
                    "username": user.username,
                    "role": groups or ("Administrator" if user.is_staff or user.is_superuser else "Other"),
                    "is_active": user.is_active,
                })

    elif report_type == "staff":
        users = User.objects.filter(
            Q(groups__name__iexact="Lecturer") |
            Q(groups__name__iexact="HOD") |
            Q(is_staff=True) |
            Q(is_superuser=True)
        ).distinct().prefetch_related("groups")
        for user in users:
            rows.append({
                "name": user.get_full_name() or user.username,
                "username": user.username,
                "email": user.email,
                "roles": ", ".join(user.groups.values_list("name", flat=True)),
                "active": user.is_active,
            })

    elif report_type == "departments":
        for department in Department.objects.all().order_by("name"):
            rows.append({
                "department": department.name,
                "courses": department.courses.count(),
                "students": Student.objects.filter(course__department=department).count(),
            })

    elif report_type == "courses-subjects":
        qs = Course.objects.select_related("department").prefetch_related("subjects")
        if filters["department"]:
            qs = qs.filter(department_id=filters["department"])
        for course in qs.order_by("name"):
            for subject in course.subjects.all():
                rows.append({
                    "department": course.department.name if course.department else "",
                    "course": course.name,
                    "course_code": course.code,
                    "subject": subject.name,
                    "subject_code": subject.code,
                })

    elif report_type == "classrooms":
        for room in Classroom.objects.all().order_by("room_name"):
            rows.append({
                "classroom": room.room_name,
                "room_number": room.room_number,
                "latitude": room.latitude,
                "longitude": room.longitude,
                "radius_meters": room.radius_meters,
            })

    elif report_type == "lecturer-assignments":
        for assignment in LecturerSubject.objects.select_related("lecturer", "subject", "subject__course"):
            rows.append({
                "lecturer": assignment.lecturer.get_full_name() or assignment.lecturer.username,
                "course": assignment.subject.course.name,
                "subject": assignment.subject.name,
                "subject_code": assignment.subject.code,
            })
        for assignment in LecturerCourse.objects.select_related("lecturer", "course"):
            rows.append({
                "lecturer": assignment.lecturer.get_full_name() or assignment.lecturer.username,
                "course": assignment.course.name,
                "subject": "All assigned course subjects",
                "subject_code": "",
            })

    elif report_type == "timetables":
        qs = Timetable.objects.select_related("course", "course__department", "subject", "lecturer")
        if filters["department"]:
            qs = qs.filter(course__department_id=filters["department"])
        if filters["course"]:
            qs = qs.filter(course_id=filters["course"])
        if filters["subject"]:
            qs = qs.filter(subject_id=filters["subject"])
        if filters["lecturer"]:
            qs = qs.filter(lecturer_id=filters["lecturer"])
        for item in qs.order_by("day", "start_time"):
            rows.append({
                "department": item.course.department.name if item.course.department else "",
                "course": item.course.name,
                "subject": item.subject.name,
                "lecturer": item.lecturer.get_full_name() or item.lecturer.username,
                "day": item.day,
                "start_time": _text(item.start_time),
                "end_time": _text(item.end_time),
                "room": item.room,
            })

    elif report_type == "academic-calendar":
        calendars = SemesterCalendar.objects.prefetch_related("periods").order_by("-uploaded_at")
        if filters["academic_year"]:
            calendars = calendars.filter(academic_year=filters["academic_year"])
        if filters["semester"]:
            calendars = calendars.filter(semester=filters["semester"])
        for calendar in calendars:
            rows.append({
                "title": calendar.title,
                "academic_year": calendar.academic_year,
                "semester": calendar.semester,
                "teaching_start_date": _text(calendar.teaching_start_date),
                "teaching_end_date": _text(calendar.teaching_end_date),
                "is_finalized": calendar.is_finalized,
                "finalized_at": _text(calendar.finalized_at),
            })
            for period in calendar.periods.all():
                rows.append({
                    "title": f"  {period.name}",
                    "academic_year": calendar.academic_year,
                    "semester": calendar.semester,
                    "teaching_start_date": _text(period.start_date),
                    "teaching_end_date": _text(period.end_date),
                    "is_finalized": period.period_type,
                    "finalized_at": "",
                })

    elif report_type in {"verification-failures", "geofence-violations", "invalid-attempts"}:
        logs = MovementLog.objects.select_related(
            "student", "session", "session__course", "session__subject"
        ).all()
        if filters["start_date"]:
            logs = logs.filter(timestamp__date__gte=filters["start_date"])
        if filters["end_date"]:
            logs = logs.filter(timestamp__date__lte=filters["end_date"])
        if filters["student_id"]:
            logs = logs.filter(student_id=filters["student_id"])
        if filters["session_id"]:
            logs = logs.filter(session_id=filters["session_id"])
        if report_type == "geofence-violations":
            logs = logs.filter(inside_geofence=False)
        elif report_type == "verification-failures":
            logs = logs.filter(
                Q(inside_geofence=False) | Q(wifi_valid=False) | Q(beacon_valid=False)
            )
        else:
            logs = logs.filter(
                Q(inside_geofence=False) | Q(wifi_valid=False) | Q(beacon_valid=False)
            )
        for log in logs.order_by("-timestamp"):
            rows.append({
                "student": log.student.full_name,
                "registration_number": log.student.reg_number,
                "session_id": log.session_id,
                "course": log.session.course.name,
                "subject": log.session.subject.name,
                "timestamp": _text(log.timestamp),
                "inside_geofence": log.inside_geofence,
                "wifi_valid": log.wifi_valid,
                "beacon_valid": log.beacon_valid,
                "latitude": log.latitude,
                "longitude": log.longitude,
            })

    elif report_type in {"session-history", "admin-activity"}:
        history = SessionChangeHistory.objects.select_related(
            "session", "session__course", "session__subject", "changed_by"
        ).all()
        if filters["start_date"]:
            history = history.filter(recorded_at__date__gte=filters["start_date"])
        if filters["end_date"]:
            history = history.filter(recorded_at__date__lte=filters["end_date"])
        if filters["course"]:
            history = history.filter(session__course_id=filters["course"])
        for event in history.order_by("-recorded_at"):
            rows.append({
                "session_id": event.session_id,
                "course": event.session.course.name,
                "subject": event.session.subject.name,
                "change_type": event.change_type,
                "changed_by": event.changed_by.get_full_name() if event.changed_by else "",
                "reason": event.reason,
                "recorded_at": _text(event.recorded_at),
                "scheduled_start": _text(event.scheduled_start),
                "scheduled_end": _text(event.scheduled_end),
                "actual_start": _text(event.actual_start),
                "actual_end": _text(event.actual_end),
            })

    elif report_type in {"institution-summary", "department-performance"}:
        sessions = _sessions_for(filters)
        departments = Department.objects.all().order_by("name")
        if filters["department"]:
            departments = departments.filter(id=filters["department"])
        for department in departments:
            department_sessions = sessions.filter(course__department=department)
            records = Attendance.objects.filter(session__in=department_sessions)
            total = records.count()
            present = records.filter(status="PRESENT").count()
            late = records.filter(status="LATE").count()
            absent = records.filter(status="ABSENT").count()
            partial = records.filter(status="PARTIAL_ATTENDANCE").count()
            rows.append({
                "department": department.name,
                "sessions": department_sessions.count(),
                "attendance_records": total,
                "present": present,
                "late": late,
                "partial": partial,
                "absent": absent,
                "attendance_rate": round(((present + late + partial) / total) * 100, 2) if total else 0,
                "students": Student.objects.filter(course__department=department).count(),
            })

    else:
        return None, filters, report_type, "Unknown report type."

    return rows, filters, report_type, message


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_report_preview(request):
    rows, filters, report_type, message = _build_report(request)
    if rows is None:
        return Response({"detail": message}, status=400)

    columns = list(rows[0].keys()) if rows else []
    return Response({
        "report_type": report_type,
        "filters": filters,
        "columns": columns,
        "rows": rows,
        "total_records": len(rows),
        "generated_at": timezone.now(),
        "message": message,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_report_filters(request):
    departments = list(Department.objects.order_by("name").values("id", "name"))
    courses = list(Course.objects.order_by("name").values("id", "name", "department_id"))
    subjects = list(Subject.objects.order_by("name").values("id", "name", "course_id"))
    lecturers = User.objects.filter(
        Q(groups__name__iexact="Lecturer") | Q(timetable__isnull=False)
    ).distinct().order_by("first_name", "last_name")
    lecturer_options = [
        {"id": user.id, "name": user.get_full_name() or user.username}
        for user in lecturers
    ]
    students = [
        {"id": item.id, "name": item.full_name, "course_id": item.course_id}
        for item in Student.objects.order_by("full_name")
    ]
    sessions = [
        {
            "id": item.id,
            "label": f"{item.date} - {item.course.name} / {item.subject.name}",
        }
        for item in AttendanceSession.objects.select_related(
            "course", "subject"
        ).order_by("-date", "-id")[:500]
    ]
    calendars = SemesterCalendar.objects.order_by("-uploaded_at")
    academic_years = list(
        calendars.values_list("academic_year", flat=True).distinct()
    )
    return Response({
        "academic_years": academic_years,
        "semesters": [
            {"value": "SEMESTER_1", "label": "Semester 1"},
            {"value": "SEMESTER_2", "label": "Semester 2"},
            {"value": "SUMMER", "label": "Summer"},
        ],
        "departments": departments,
        "courses": courses,
        "subjects": subjects,
        "lecturers": lecturer_options,
        "students": students,
        "sessions": sessions,
    })

# ============================================================
# ADMIN REPORT EXPORTS: PDF, EXCEL AND CSV
# ============================================================

import csv
import io
import json

from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from xml.sax.saxutils import escape


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_report_export(request):
    rows, filters, report_type, message = _build_report(request)

    if rows is None:
        return Response({"detail": message}, status=400)

    export_format = request.query_params.get("format", "").lower()

    if export_format not in ("pdf", "xlsx", "csv"):
        return Response(
            {"detail": "Unsupported export format. Use pdf, xlsx or csv."},
            status=400
        )

    columns = list(rows[0].keys()) if rows else []

    def cell_value(value):
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    filename = f"geoattend-{report_type}"

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        if columns:
            writer.writerow(columns)
            for row in rows:
                writer.writerow([cell_value(row.get(column)) for column in columns])

        response = HttpResponse(
            output.getvalue(),
            content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}.csv"'
        )
        return response

    if export_format == "xlsx":
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Report"

        if columns:
            worksheet.append(columns)

            for row in rows:
                worksheet.append([
                    cell_value(row.get(column)) for column in columns
                ])

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions

        for column_cells in worksheet.columns:
            max_length = max(
                (len(str(cell.value or "")) for cell in column_cells),
                default=10
            )
            worksheet.column_dimensions[
                column_cells[0].column_letter
            ].width = min(max(max_length + 2, 12), 40)

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}.xlsx"'
        )
        return response

    # PDF export
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=16,
        spaceAfter=8
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["BodyText"],
        fontSize=7,
        leading=9,
        wordWrap="CJK"
    )
    header_style = ParagraphStyle(
        "ReportHeader",
        parent=cell_style,
        textColor=colors.white,
        fontName="Helvetica-Bold"
    )

    story = [
        Paragraph("GeoAttend - " + escape(report_type.replace("-", " ").title()), title_style),
        Paragraph(
            "Generated: " + escape(str(timezone.localtime(timezone.now()))),
            styles["Normal"]
        ),
        Spacer(1, 8)
    ]

    if columns:
        table_data = [[
            Paragraph(escape(str(column).replace("_", " ").title()), header_style)
            for column in columns
        ]]

        for row in rows:
            table_data.append([
                Paragraph(
                    escape(cell_value(row.get(column))) or "—",
                    cell_style
                )
                for column in columns
            ])

        available_width = landscape(A4)[0] - 24 * mm
        column_width = available_width / max(len(columns), 1)

        table = Table(
            table_data,
            colWidths=[column_width] * len(columns),
            repeatRows=1
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white, colors.HexColor("#f1f5f9")
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph(
            "No records found for the selected report and filters.",
            styles["Normal"]
        ))

    document.build(story)
    output.seek(0)

    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}.pdf"'
    )
    return response
