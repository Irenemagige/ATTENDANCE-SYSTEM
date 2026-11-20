import io
import re
from datetime import datetime

import pdfplumber
import pymupdf
import pytesseract
from PIL import Image
from openpyxl import load_workbook

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

REVERSE_DAY_MAP = {value: key for key, value in DAY_MAP.items()}


def clean_name(value):
    value = str(value or "").strip()

    if value.lower() == "clouds and devops":
        value = "Cloud and Devops"

    if value.startswith("(Lecturer ") and value.endswith(")"):
        value = value[len("(Lecturer "):-1].strip()

    return value


def parse_time_range(value):
    value = str(value or "").strip()
    value = value.replace("â€“", "-").replace("â€”", "-")

    if "-" not in value:
        raise ValueError("Invalid time range.")

    start_text, end_text = [
        part.strip() for part in value.split("-", 1)
    ]

    start_time = datetime.strptime(start_text, "%H:%M").time()
    end_time = datetime.strptime(end_text, "%H:%M").time()

    if start_time >= end_time:
        raise ValueError("Start time must be before end time.")

    return start_time.strftime("%H:%M"), end_time.strftime("%H:%M")


def find_course(label):
    label = str(label or "").strip()

    course = Course.objects.filter(name__iexact=label).first()
    if course:
        return course

    match = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", label)

    if match:
        code = match.group(2).strip()
        name = match.group(1).strip()

        course = Course.objects.filter(code__iexact=code).first()
        if course:
            return course

        return Course.objects.filter(name__iexact=name).first()

    return Course.objects.filter(code__iexact=label).first()


def find_lecturer(label):
    label = clean_name(label)

    lecturer = User.objects.filter(username__iexact=label).first()
    if lecturer:
        return lecturer

    lecturer = User.objects.filter(first_name__iexact=label).first()
    if lecturer:
        return lecturer

    parts = label.split()

    if len(parts) >= 2:
        lecturer = User.objects.filter(
            first_name__iexact=parts[0],
            last_name__iexact=" ".join(parts[1:]),
        ).first()

    return lecturer


def extract_cell_names(value):
    lines = [
        clean_name(line)
        for line in str(value or "").splitlines()
        if str(line).strip()
    ]

    if len(lines) < 2:
        return None, None

    return lines[0], lines[1]


def build_raw_entry(course_label, subject_label, lecturer_label,
                    day_label, time_text, source):
    try:
        start_time, end_time = parse_time_range(time_text)
    except ValueError as exc:
        raise ValueError(
            f"{source}: Invalid time '{time_text}'. {exc}"
        )

    if day_label not in DAY_MAP:
        raise ValueError(f"{source}: Unsupported weekday '{day_label}'.")

    course = find_course(course_label)
    subject = None
    lecturer = None

    if course:
        subject = Subject.objects.filter(
            course=course,
            name__iexact=subject_label,
        ).first()

        if subject:
            lecturer = find_lecturer(lecturer_label)

    return {
        "source": source,
        "course_label": str(course_label).strip(),
        "department_label": course.department.name if course else "",
        "subject_label": clean_name(subject_label),
        "lecturer_label": clean_name(lecturer_label),
        "day_label": day_label,
        "day": DAY_MAP[day_label],
        "start_time": start_time,
        "end_time": end_time,
        "room": "",
        "course_id": course.id if course else None,
        "subject_id": subject.id if subject else None,
        "lecturer_id": lecturer.id if lecturer else None,
        "issues": [],
    }


def extract_excel(uploaded_file):
    try:
        workbook = load_workbook(uploaded_file, data_only=True)
    except Exception:
        raise ValueError(
            "This is not a valid .xlsx workbook. "
            "Please upload a genuine Excel .xlsx timetable."
        )

    entries = []
    errors = []

    for sheet in workbook.worksheets:
        course_label = sheet.title.strip()
        header_row = None
        headers = {}

        for row_number in range(1, sheet.max_row + 1):
            current_headers = {}

            for column in range(1, sheet.max_column + 1):
                value = sheet.cell(row=row_number, column=column).value

                if value:
                    current_headers[column] = str(value).strip()

            if any(value.lower() == "time" for value in current_headers.values()):
                header_row = row_number
                headers = current_headers
                break

        if header_row is None:
            errors.append(
                f"Sheet '{course_label}': Could not find a Time header."
            )
            continue

        time_column = next(
            column for column, value in headers.items()
            if value.lower() == "time"
        )

        day_columns = {
            column: value
            for column, value in headers.items()
            if value.lower() in [day.lower() for day in DAY_MAP]
        }

        if not day_columns:
            errors.append(
                f"Sheet '{course_label}': No weekday columns were found."
            )
            continue

        for row_number in range(header_row + 1, sheet.max_row + 1):
            time_value = sheet.cell(
                row=row_number,
                column=time_column,
            ).value

            if not time_value:
                continue

            for column, day_label in day_columns.items():
                cell_value = sheet.cell(
                    row=row_number,
                    column=column,
                ).value

                if not cell_value:
                    continue

                subject_name, lecturer_name = extract_cell_names(cell_value)

                source = f"{sheet.title}, row {row_number}, {day_label}"

                if not subject_name or not lecturer_name:
                    errors.append(
                        f"{source}: Cell must contain subject on the first "
                        "line and lecturer on the second line."
                    )
                    continue

                try:
                    entry = build_raw_entry(
                        course_label,
                        subject_name,
                        lecturer_name,
                        day_label,
                        time_value,
                        source,
                    )
                    entries.append(entry)
                except ValueError as exc:
                    errors.append(str(exc))

    return entries, errors


def _extract_digital_pdf(uploaded_file):
    entries = []
    errors = []

    try:
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""

                course_match = re.search(
                    r"Course:\s*(.+?)(?:\s*\|\s*Academic Year|$)",
                    page_text,
                    re.IGNORECASE,
                )

                if not course_match:
                    errors.append(
                        f"Page {page_number}: Could not identify the course."
                    )
                    continue

                course_label = course_match.group(1).strip()
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

                    for index, row in enumerate(table):
                        values = [
                            str(value or "").strip()
                            for value in row
                        ]

                        if any(value.lower() == "time" for value in values):
                            header_index = index
                            headers = values
                            break

                    if header_index is None:
                        continue

                    time_index = next(
                        index for index, value in enumerate(headers)
                        if value.lower() == "time"
                    )

                    day_columns = {
                        index: next(
                            day for day in DAY_MAP
                            if value.lower() == day.lower()
                        )
                        for index, value in enumerate(headers)
                        if value.lower() in [
                            day.lower() for day in DAY_MAP
                        ]
                    }

                    for row_number, row in enumerate(
                        table[header_index + 1:],
                        start=header_index + 2,
                    ):
                        if time_index >= len(row) or not row[time_index]:
                            continue

                        time_value = str(row[time_index]).strip()

                        for column, day_label in day_columns.items():
                            if column >= len(row) or not row[column]:
                                continue

                            subject_name, lecturer_name = extract_cell_names(
                                row[column]
                            )

                            source = (
                                f"Page {page_number}, row {row_number}, "
                                f"{day_label}"
                            )

                            if not subject_name or not lecturer_name:
                                errors.append(
                                    f"{source}: Cell must contain a subject "
                                    "and lecturer."
                                )
                                continue

                            try:
                                entry = build_raw_entry(
                                    course_label,
                                    subject_name,
                                    lecturer_name,
                                    day_label,
                                    time_value,
                                    source,
                                )
                                entries.append(entry)
                            except ValueError as exc:
                                errors.append(str(exc))

    except Exception as exc:
        raise ValueError(f"Could not process the PDF: {str(exc)}")

    return entries, errors



def extract_ocr_layout(image, source):
    """
    Extract timetable entries using OCR coordinates.
    Time rows determine vertical positions; weekday headings
    determine horizontal columns.
    """
    import os

    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    image = image.convert("RGB")

    data = pytesseract.image_to_data(
        image,
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

    grouped = {}

    for index, raw_text in enumerate(data["text"]):
        text = str(raw_text or "").strip()

        if not text:
            continue

        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError):
            continue

        if confidence < 0:
            continue

        key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )

        word = {
            "text": text,
            "left": int(data["left"][index]),
            "top": int(data["top"][index]),
            "width": int(data["width"][index]),
            "height": int(data["height"][index]),
        }

        word["center"] = word["left"] + word["width"] / 2
        word["center_y"] = word["top"] + word["height"] / 2

        grouped.setdefault(key, []).append(word)

    lines = []

    for group_words in grouped.values():
        group_words.sort(key=lambda item: item["left"])

        lines.append({
            "words": group_words,
            "top": min(word["top"] for word in group_words),
            "bottom": max(
                word["top"] + word["height"]
                for word in group_words
            ),
            "center_y": sum(
                word["center_y"] for word in group_words
            ) / len(group_words),
            "text": " ".join(
                word["text"] for word in group_words
            ),
        })

    lines.sort(key=lambda item: item["center_y"])

    if not lines:
        return [], [f"{source}: OCR could not recognize any text."]

    full_text = "\n".join(line["text"] for line in lines)

    report_terms = (
        "attendance report",
        "student attendance",
        "attendance summary",
        "attendance percentage",
    )

    if any(term in full_text.lower() for term in report_terms):
        return [], [
            f"{source}: This appears to be an attendance report, "
            "not a timetable."
        ]

    course_match = re.search(
        r"(?:Course|Programme|Program)\s*:\s*(.+)",
        full_text,
        re.IGNORECASE,
    )

    if not course_match:
        return [], [
            f"{source}: Could not identify the course or programme."
        ]

    course_label = course_match.group(1).strip()

    day_aliases = {
        "monday": "Monday",
        "mon": "Monday",
        "tuesday": "Tuesday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "wednesday": "Wednesday",
        "wed": "Wednesday",
        "thursday": "Thursday",
        "thu": "Thursday",
        "thur": "Thursday",
        "thurs": "Thursday",
        "friday": "Friday",
        "fri": "Friday",
        "saturday": "Saturday",
        "sat": "Saturday",
        "sunday": "Sunday",
        "sun": "Sunday",
    }

    header = None
    day_positions = {}
    time_header_center = None

    for line in lines:
        normalized = [
            re.sub(r"[^a-z]", "", word["text"].lower())
            for word in line["words"]
        ]

        if "time" not in normalized:
            continue

        candidate_days = {}

        for word, token in zip(line["words"], normalized):
            if token in day_aliases:
                candidate_days[day_aliases[token]] = word["center"]

        if candidate_days:
            header = line
            day_positions = candidate_days

            for word, token in zip(line["words"], normalized):
                if token == "time":
                    time_header_center = word["center"]
                    break

            break

    if not header or not time_header_center:
        return [], [
            f"{source}: Could not identify the Time and weekday headings."
        ]

    ordered_days = sorted(
        day_positions.items(),
        key=lambda item: item[1],
    )

    boundaries = []

    for index, (day, center) in enumerate(ordered_days):
        left_boundary = (
            (time_header_center + center) / 2
            if index == 0
            else (ordered_days[index - 1][1] + center) / 2
        )

        right_boundary = (
            (center + ordered_days[index + 1][1]) / 2
            if index < len(ordered_days) - 1
            else image.width + 1
        )

        boundaries.append((day, left_boundary, right_boundary))

    time_pattern = re.compile(
        r"(\d{1,2}[:.]\d{2})\s*[-–—]\s*(\d{1,2}[:.]\d{2})"
    )

    time_rows = []

    for line in lines:
        match = time_pattern.search(line["text"])

        if match:
            time_rows.append({
                "center_y": line["center_y"],
                "time": (
                    match.group(1).replace(".", ":")
                    + "-"
                    + match.group(2).replace(".", ":")
                ),
            })

    time_rows.sort(key=lambda item: item["center_y"])

    if not time_rows:
        return [], [
            f"{source}: OCR could not detect timetable time ranges."
        ]

    # Calculate vertical boundaries between timetable rows.
    row_boundaries = []

    for index, row in enumerate(time_rows):
        if index == 0:
            top = header["bottom"]
        else:
            top = (
                time_rows[index - 1]["center_y"]
                + row["center_y"]
            ) / 2

        if index < len(time_rows) - 1:
            bottom = (
                row["center_y"]
                + time_rows[index + 1]["center_y"]
            ) / 2
        else:
            previous_gap = (
                row["center_y"] - time_rows[index - 1]["center_y"]
                if index > 0 else image.height - row["center_y"]
            )
            bottom = row["center_y"] + previous_gap / 2

        row_boundaries.append((top, bottom))

    entries = []
    errors = []

    for row_index, row in enumerate(time_rows):
        top, bottom = row_boundaries[row_index]

        for day, left_boundary, right_boundary in boundaries:
            cell_lines = []

            for line in lines:
                if not (top <= line["center_y"] <= bottom):
                    continue

                cell_words = [
                    word["text"]
                    for word in line["words"]
                    if left_boundary < word["center"] <= right_boundary
                ]

                if cell_words:
                    cell_lines.append(" ".join(cell_words))

            cell_text = "\n".join(cell_lines).strip()

            if not cell_text:
                continue

            subject_name, lecturer_name = extract_cell_names(cell_text)

            if not subject_name or not lecturer_name:
                errors.append(
                    f"{source}, {day}, {row['time']}: "
                    "Could not identify both subject and lecturer. "
                    f"Recognized text: {cell_text}"
                )
                continue

            try:
                entry = build_raw_entry(
                    course_label,
                    subject_name,
                    lecturer_name,
                    day,
                    row["time"],
                    f"{source}, {day}, {row['time']}",
                )
                entries.append(entry)

            except ValueError as exc:
                errors.append(str(exc))

    if not entries and not errors:
        errors.append(f"{source}: No timetable entries were detected.")

    return entries, errors
def extract_ocr_image(image, source):
    try:
        return extract_ocr_layout(image, source)
    except Exception as exc:
        raise ValueError(
            f"OCR processing failed for {source}: {str(exc)}"
        )


def extract_pdf(uploaded_file):
    file_bytes = uploaded_file.read()

    # First try the existing digital PDF table extraction.
    try:
        digital_entries, digital_errors = _extract_digital_pdf(
            io.BytesIO(file_bytes)
        )
    except Exception:
        digital_entries, digital_errors = [], []

    if digital_entries:
        return digital_entries, digital_errors

    # If the PDF has no extractable timetable, render pages and use OCR.
    entries = []
    errors = []

    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )

        if document.page_count == 0:
            raise ValueError("The PDF contains no pages.")

        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(3, 3),
                alpha=False,
            )

            image = Image.open(
                io.BytesIO(pixmap.tobytes("png"))
            )

            page_entries, page_errors = extract_ocr_image(
                image,
                f"PDF page {page_number}",
            )

            entries.extend(page_entries)
            errors.extend(page_errors)

        document.close()

    except Exception as exc:
        raise ValueError(
            f"Could not process the PDF using OCR: {str(exc)}"
        )

    if not entries and not errors:
        errors.append(
            "No timetable entries could be extracted from this PDF."
        )

    return entries, errors


def get_matching_options():
    courses = Course.objects.select_related("department").order_by(
        "department__name", "name"
    )

    subjects = Subject.objects.select_related("course").order_by("name")

    lecturer_ids = LecturerCourse.objects.values_list(
        "lecturer_id", flat=True
    ).distinct()

    lecturers = User.objects.filter(
        id__in=lecturer_ids
    ).order_by("first_name", "last_name", "username")

    return {
        "departments": list(
            Course.objects.values(
                "department_id",
                "department__name",
            ).distinct().order_by("department__name")
        ),
        "courses": [
            {
                "id": item.id,
                "name": item.name,
                "code": item.code,
                "department_id": item.department_id,
                "department": item.department.name,
            }
            for item in courses
        ],
        "subjects": [
            {
                "id": item.id,
                "name": item.name,
                "code": item.code,
                "course_id": item.course_id,
            }
            for item in subjects
        ],
        "lecturers": [
            {
                "id": item.id,
                "name": item.get_full_name() or item.username,
                "username": item.username,
            }
            for item in lecturers
        ],
    }


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def preview_timetable_import(request):
    uploaded_file = request.FILES.get("file")

    if not uploaded_file:
        return Response(
            {"error": "Please select a timetable file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded_file.size > 10 * 1024 * 1024:
        return Response(
            {"error": "The timetable file must not exceed 10 MB."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    filename = uploaded_file.name.lower()

    try:
        if filename.endswith(".pdf"):
            entries, errors = extract_pdf(uploaded_file)
        elif filename.endswith(".xlsx"):
            entries, errors = extract_excel(uploaded_file)
        elif filename.endswith((".jpg", ".jpeg", ".png")):
            image = Image.open(uploaded_file)
            entries, errors = extract_ocr_image(
                image,
                uploaded_file.name,
            )
        else:
            return Response(
                {
                    "error": (
                        "Unsupported file format. Upload a genuine "
                        ".xlsx, .pdf, .jpg, .jpeg or .png timetable."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "message": "Preview generated. No timetable records were saved.",
            "entries": entries,
            "entry_count": len(entries),
            "error_count": len(errors),
            "errors": errors,
            "options": get_matching_options(),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAdminOrStaff])
def confirm_timetable_import(request):
    entries = request.data.get("entries")

    if not isinstance(entries, list) or not entries:
        return Response(
            {"error": "No timetable entries were provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validated = []
    errors = []
    seen = set()

    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            errors.append(f"Entry {index}: Invalid entry format.")
            continue

        course = Course.objects.filter(
            id=item.get("course_id")
        ).first()

        subject = Subject.objects.filter(
            id=item.get("subject_id"),
            course=course,
        ).first() if course else None

        lecturer = User.objects.filter(
            id=item.get("lecturer_id")
        ).first()

        day = item.get("day")
        start_text = str(item.get("start_time", "")).strip()
        end_text = str(item.get("end_time", "")).strip()

        if not course:
            errors.append(f"Entry {index}: Select an existing course.")
            continue

        if not subject:
            errors.append(
                f"Entry {index}: Select a subject belonging to "
                f"{course.name}."
            )
            continue

        if not lecturer:
            errors.append(f"Entry {index}: Select an existing lecturer.")
            continue

        if day not in REVERSE_DAY_MAP:
            errors.append(f"Entry {index}: Invalid weekday.")
            continue

        try:
            start_time = datetime.strptime(start_text, "%H:%M").time()
            end_time = datetime.strptime(end_text, "%H:%M").time()
        except ValueError:
            errors.append(f"Entry {index}: Invalid time.")
            continue

        if start_time >= end_time:
            errors.append(
                f"Entry {index}: Start time must be before end time."
            )
            continue

        if not LecturerCourse.objects.filter(
            lecturer=lecturer,
            course=course,
        ).exists():
            errors.append(
                f"Entry {index}: Lecturer is not assigned to "
                f"{course.name}."
            )
            continue

        if not LecturerSubject.objects.filter(
            lecturer=lecturer,
            subject=subject,
        ).exists():
            errors.append(
                f"Entry {index}: Lecturer is not assigned to "
                f"{subject.name}."
            )
            continue

        key = (
            course.id,
            subject.id,
            lecturer.id,
            day,
            start_text,
            end_text,
        )

        if key in seen:
            errors.append(
                f"Entry {index}: Duplicate entry in this upload."
            )
            continue

        seen.add(key)

        validated.append({
            "course": course,
            "subject": subject,
            "lecturer": lecturer,
            "day": day,
            "start_time": start_time,
            "end_time": end_time,
            "room": str(item.get("room", ""))[:50],
        })

    if errors:
        return Response(
            {
                "error": "Validation failed. Nothing was imported.",
                "errors": errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    created = 0
    skipped = 0

    with transaction.atomic():
        for item in validated:
            exists = Timetable.objects.filter(
                course=item["course"],
                subject=item["subject"],
                lecturer=item["lecturer"],
                day=item["day"],
                start_time=item["start_time"],
                end_time=item["end_time"],
            ).exists()

            if exists:
                skipped += 1
                continue

            Timetable.objects.create(**item)
            created += 1

    return Response(
        {
            "message": "Timetable import completed.",
            "created": created,
            "skipped": skipped,
        },
        status=status.HTTP_201_CREATED,
    )


