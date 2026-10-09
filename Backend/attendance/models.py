from django.db import models
from django.utils import timezone
from students.models import Student
from courses.models import Course, Subject
from django.conf import settings
from courses.models import Classroom
from django.conf import settings


# =========================
# ATTENDANCE SESSION
# =========================
class AttendanceSession(models.Model):

    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    timetable = models.ForeignKey(
        "courses.Timetable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    date = models.DateField(
        default=timezone.now
    )

    start_time = models.DateTimeField(
        default=timezone.now
    )

    end_time = models.DateTimeField(
        null=True,
        blank=True
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True
    )

    auto_closed = models.BooleanField(
        default=False
    )

    checkout_deadline = models.DateTimeField(
        null=True,
        blank=True
    )

    latitude = models.FloatField()
    longitude = models.FloatField()

    radius_meters = models.IntegerField(
        default=100
    )

    is_active = models.BooleanField(
        default=True
    )

    is_override = models.BooleanField(
        default=False
    )

    override_reason = models.TextField(
        null=True,
        blank=True
    )

    override_duration_minutes = models.IntegerField(
        default=120,
        help_text="Duration for postponed/replacement classes in minutes"
    )

    allowed_wifi_bssid = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    allowed_beacon_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.course.name} - {self.subject.name}"

# =========================
# ATTENDANCE
# =========================
class Attendance(models.Model):

    STATUS_CHOICES = [
    ("PRESENT", "Present"),
    ("LATE", "Late"),
    ("PARTIAL_ATTENDANCE", "Partial Attendance"),
    ("INVALID_ATTEMPT", "Invalid Attempt"),
    ("ABSENT", "Absent"),
    
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE)

    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PRESENT"
    )
    attendance_percentage = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    default=0
    )
class MovementLog(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="movement_logs"
    )

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="movement_logs"
    )

    latitude = models.FloatField()

    longitude = models.FloatField()

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    inside_geofence = models.BooleanField(
        default=True
    )

    wifi_valid = models.BooleanField(
        default=False
    )

    beacon_valid = models.BooleanField(
        default=False
    )


    def __str__(self):
        return f"{self.student} - {self.timestamp}"

# =========================
# SESSION CHANGE HISTORY
# =========================
class SessionChangeHistory(models.Model):

    CHANGE_TYPE_CHOICES = [
        ("SESSION_STARTED", "Normal Session Started"),
        ("OVERRIDE_STARTED", "Override Session Started"),
        ("SESSION_ENDED", "Session Ended Manually"),
        ("SESSION_AUTO_CLOSED", "Session Closed Automatically"),
    ]

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.PROTECT,
        related_name="change_history",
    )

    change_type = models.CharField(
        max_length=30,
        choices=CHANGE_TYPE_CHOICES,
    )

    # Snapshot of the original timetable times
    scheduled_start_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    scheduled_end_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Actual times associated with this history event
    actual_start_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    actual_end_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_change_history",
    )

    reason = models.TextField(
        blank=True,
        default="",
    )

    recorded_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return (
            f"{self.get_change_type_display()} - "
            f"{self.session.course.name} - "
            f"{self.session.subject.name}"
        )