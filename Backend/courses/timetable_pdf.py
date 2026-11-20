import io
import re
from datetime import datetime

import pdfplumber

from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.permissions import IsAdminOrStaff
from courses.models import (
    Course,
    Subject,
    LecturerCourse,
    LecturerSubject,
    Timetable,
)

User = get_user_model()

DAY_MAP = {
    "Monday": "MON",
    "Tuesday": "TUE",
    "Wednesday": "WED",
    "Thursday": "THU",
    "Friday": "FRI",
    "Saturday": "SAT",
    "Sunday": "SUN",
}


def find_pdf_course(course_label):
    course = Course.objects.filter(name__iexact=course_label).first()

    if course:
        return course

    code_match = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", course_label)

    if code_match:
        course_name = code_match.group(1).strip()
        course_code = code_match.group(2).strip()

        course = Course.objects.filter(code__iexact=course_code).first()

        if course:
            return course

        course = Course.objects.filter(name__iexact=course_name).first()

    return course


def find_pdf_lecturer(lecturer_name):
    lecturer = User.objects.filter(
        username__iexact=lecturer_name
    ).first()

    if lecturer:
        return lecturer

    name_parts = lecturer_name.split()

    if len(name_parts) >= 2:
        lecturer = User.objects.filter(
            first_name__iexact=name_parts[0],
            last_name__iexact=" ".join(name_parts[1:]),
        ).first()

        if lecturer:
            return lecturer

    return User.objects.filter(
        first_name__iexact=lecturer_name
    ).first()


def validate_pdf_entry(course, subject_name, lecturer_name, day, start_text, end_text):
    subject_name = subject_name.strip()
    lecturer_name = lecturer_name.strip()

    if subject_name.lower() == "clouds and devops":
        subject_name = "Cloud and Devops"

    if lecturer_name.startswith("(Lecturer ") and lecturer_name.endswith(")"):
        lecturer_name = lecturer_name[len("(Lecturer "):-1].strip()

    subject = Subject.objects.filter(
        course=course,
        name__iexact=subject_name,
    ).first()

    if not subject:
        return None, f"Subject '{subject_name}' was not found under {course.name}."

    lecturer = find_pdf_lecturer(lecturer_name)

    if not lecturer:
        return None, f"Lecturer '{lecturer_name}' was not found."

    if not LecturerCourse.objects.filter(
        lecturer=lecturer,
        course=course,
    ).exists():
        return None, f"{lecturer_name} is not assigned to {course.name}."

    if not LecturerSubject.objects.filter(
        lecturer=lecturer,
        subject=subject,
    ).exists():
        return None, f"{lecturer_name} is not assigned to {subject_name}."

    try:
        start_time = datetime.strptime(start_text.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_text.strip(), "%H:%M").time()
    except ValueError:
        return None, f"Invalid time range: {start_text} - {end_text}."

    if start_time >= end_time:
        return None, "The start time must be before the end time."

    return {
        "course_id": course.id,
        "course": course.name,
        "course_code": course.code,
        "subject_id": subject.id,
        "subject": subject.name,
        "subject_code": subject.code,
        "lecturer_id": lecturer.id,
        "lecturer": lecturer.get_full_name() or lecturer.username,
        "day": DAY_MAP[day],
        "day_label": day,
        "start_time": start_time.strftime("%H:%M"),
        "end_time": end_time.strftime("%H:%M"),
        "room": "",
    }, None


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def preview_timetable_pdf(request):
    uploaded_file = request.FILES.get("file")

    if not uploaded_file:
        return Response(
            {"error": "Please select a PDF timetable."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not uploaded_file.name.lower().endswith(".pdf"):
        return Response(
            {"error": "Only PDF files are accepted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > 10 * 1024 * 1024:
        return Response(
            {"error": "The PDF must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_entries = []
    errors = []
    extracted_text_found = False

    try:
        pdf_bytes = uploaded_file.read()

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:

            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""

                if page_text.strip():
                    extracted_text_found = True

                course_match = re.search(
                    r"Course:\s*(.+?)(?:\s*\|\s*Academic Year|$)",
                    page_text,
                    re.IGNORECASE,
                )

                if not course_match:
                    errors.append(
                        f"Page {page_number}: Could not identify the course name."
                    )
                    continue

                course_label = course_match.group(1).strip()
                course = find_pdf_course(course_label)

                if not course:
                    errors.append(
                        f"Page {page_number}: Course '{course_label}' "
                        "was not found in GeoAttend."
                    )
                    continue

                tables = page.extract_tables()

                if not tables:
                    errors.append(
                        f"Page {page_number}: No timetable table was detected."
                    )
                    continue

                for table in tables:
                    if not table:
                        continue

                    header_index = None
                    headers = []

                    for row_index, row in enumerate(table):
                        normalized = [
                            str(value).strip() if value else ""
                            for value in row
                        ]

                        if any(value.lower() == "time" for value in normalized):
                            header_index = row_index
                            headers = normalized
                            break

                    if header_index is None:
                        continue

                    time_index = next(
                        index for index, value in enumerate(headers)
                        if value.lower() == "time"
                    )

                    day_columns = {}

                    for column_index, value in enumerate(headers):
                        for day_name in DAY_MAP:
                            if value.lower() == day_name.lower():
                                day_columns[column_index] = day_name

                    if not day_columns:
                        errors.append(
                            f"Page {page_number}: No weekday columns were found."
                        )
                        continue

                    for row_index, row in enumerate(table[header_index + 1:], start=header_index + 2):
                        if time_index >= len(row) or not row[time_index]:
                            continue

                        time_text = str(row[time_index]).strip()
                        time_text = time_text.replace("–", "-").replace("—", "-")

                        if "-" not in time_text:
                            errors.append(
                                f"Page {page_number}, row {row_index}: "
                                f"Invalid time '{time_text}'."
                            )
                            continue

                        start_text, end_text = [
                            value.strip()
                            for value in time_text.split("-", 1)
                        ]

                        for column_index, day_name in day_columns.items():
                            if column_index >= len(row):
                                continue

                            cell_value = row[column_index]

                            if not cell_value:
                                continue

                            lines = [
                                line.strip()
                                for line in str(cell_value).splitlines()
                                if line.strip()
                            ]

                            if len(lines) < 2:
                                errors.append(
                                    f"Page {page_number}, {day_name}, "
                                    f"{time_text}: Cell must contain the subject "
                                    "on the first line and lecturer on the second line."
                                )
                                continue

                            entry, error = validate_pdf_entry(
                                course,
                                lines[0],
                                lines[1],
                                day_name,
                                start_text,
                                end_text,
                            )

                            if error:
                                errors.append(
                                    f"{course.name}, {day_name}, "
                                    f"{time_text}: {error}"
                                )
                                continue

                            duplicate = Timetable.objects.filter(
                                course_id=entry["course_id"],
                                subject_id=entry["subject_id"],
                                lecturer_id=entry["lecturer_id"],
                                day=entry["day"],
                                start_time=entry["start_time"],
                                end_time=entry["end_time"],
                            ).exists()

                            if duplicate:
                                errors.append(
                                    f"{course.name}, {day_name}, {time_text}: "
                                    f"{entry['subject']} already exists in the timetable."
                                )
                                continue

                            valid_entries.append(entry)

        if not extracted_text_found:
            return Response(
                {
                    "error": (
                        "This PDF appears to be scanned or image-based. "
                        "Digital PDF extraction could not find selectable text. "
                        "Scanned PDF OCR will be enabled in the next implementation stage."
                    ),
                    "entries": [],
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as exc:
        return Response(
            {
                "error": f"Could not process this PDF: {str(exc)}",
                "entries": [],
                "errors": errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "message": "PDF preview generated. No timetable records have been saved.",
            "entries": valid_entries,
            "valid_count": len(valid_entries),
            "error_count": len(errors),
            "errors": errors,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def confirm_timetable_pdf(request):
    entries = request.data.get("entries")

    if not isinstance(entries, list) or not entries:
        return Response(
            {"error": "No timetable entries were provided for confirmation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated_entries = []
    errors = []

    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            errors.append(f"Entry {index}: Invalid entry format.")
            continue

        course = Course.objects.filter(
            id=item.get("course_id")
        ).first()

        if not course:
            errors.append(f"Entry {index}: Course was not found.")
            continue

        day_label = item.get("day_label")

        if day_label not in DAY_MAP:
            errors.append(f"Entry {index}: Invalid weekday.")
            continue

        result, error = validate_pdf_entry(
            course,
            str(item.get("subject", "")),
            str(item.get("lecturer", "")),
            day_label,
            str(item.get("start_time", "")),
            str(item.get("end_time", "")),
        )

        if error:
            errors.append(f"Entry {index}: {error}")
            continue

        validated_entries.append(result)

    if errors:
        return Response(
            {
                "error": "Some entries failed validation. Nothing was imported.",
                "errors": errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    created_count = 0
    skipped_count = 0

    with transaction.atomic():
        for entry in validated_entries:
            exists = Timetable.objects.filter(
                course_id=entry["course_id"],
                subject_id=entry["subject_id"],
                lecturer_id=entry["lecturer_id"],
                day=entry["day"],
                start_time=entry["start_time"],
                end_time=entry["end_time"],
            ).exists()

            if exists:
                skipped_count += 1
                continue

            Timetable.objects.create(
                course_id=entry["course_id"],
                subject_id=entry["subject_id"],
                lecturer_id=entry["lecturer_id"],
                day=entry["day"],
                start_time=entry["start_time"],
                end_time=entry["end_time"],
                room=entry.get("room", ""),
            )

            created_count += 1

    return Response(
        {
            "message": "PDF timetable import completed.",
            "created": created_count,
            "skipped": skipped_count,
        },
        status=status.HTTP_201_CREATED,
    )