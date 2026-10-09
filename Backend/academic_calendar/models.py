
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


class SemesterCalendar(models.Model):
    SEMESTER_CHOICES = [
        ("SEMESTER_1", "Semester One"),
        ("SEMESTER_2", "Semester Two"),
        ("SUMMER", "Summer Semester"),
    ]

    title = models.CharField(max_length=200)

    academic_year = models.CharField(
        max_length=9,
        help_text="Example: 2026/2027",
    )

    semester = models.CharField(
        max_length=20,
        choices=SEMESTER_CHOICES,
    )

    document = models.FileField(
        upload_to="semester_calendars/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "doc", "docx"]
            )
        ],
    )

    # Structured teaching dates extracted from the uploaded calendar.
    teaching_start_date = models.DateField(
        null=True,
        blank=True,
    )

    teaching_end_date = models.DateField(
        null=True,
        blank=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_semester_calendars",
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.academic_year})"

    class Meta:
        ordering = ["-uploaded_at"]


class AcademicCalendarPeriod(models.Model):
    PERIOD_TYPES = [
        ("BREAK", "Official Academic Break"),
        ("REVISION", "Revision Period"),
        ("EXAM", "Examination Period"),
        ("OTHER", "Other Excluded Period"),
    ]

    calendar = models.ForeignKey(
        SemesterCalendar,
        on_delete=models.CASCADE,
        related_name="periods",
    )

    name = models.CharField(max_length=200)

    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPES,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    notes = models.TextField(blank=True)

    def __str__(self):
        return (
            f"{self.name}: "
            f"{self.start_date} to {self.end_date}"
        )

    class Meta:
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="calendar_period_end_after_start",
            )
        ]