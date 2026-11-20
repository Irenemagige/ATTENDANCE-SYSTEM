from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

# -------------------------
# DEVICE MODEL
# -------------------------
class UserDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device_id = models.CharField(max_length=255, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_id}"


# -------------------------
# OTP MODEL
# -------------------------
class OTP(models.Model):
    PURPOSE_CHOICES = [
        ("device_verification", "Device Verification"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return (not self.is_used) and (not self.is_expired())

    def __str__(self):
        return f"{self.user.username} - {self.code}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)


# -------------------------
# SESSION STATE (CLEAN CORE)
# -------------------------
class UserSessionState(models.Model):

    STATE_CHOICES = [
        ("UNAUTHENTICATED", "Unauthenticated"),
        ("DEVICE_VERIFIED", "Device Verified"),
        ("GEOFENCE_PASSED", "Geofence Passed"),
        ("FINGERPRINT_REQUIRED", "Fingerprint Required"),
        ("FINGERPRINT_FAILED", "Fingerprint Failed"),
        ("OTP_REQUIRED", "OTP Required"),
        ("ATTENDANCE_GRANTED", "Attendance Granted"),
        ("CHECKED_IN", "Checked In"),
        ("CHECKED_OUT", "Checked Out"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    current_state = models.CharField(
        max_length=50,
        choices=STATE_CHOICES,
        default="UNAUTHENTICATED"
    )

    # tracking flags (optional but consistent)
    device_verified = models.BooleanField(default=False)
    geofence_verified = models.BooleanField(default=False)
    fingerprint_verified = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)

    fingerprint_attempts = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    def set_state(self, new_state):
        self.current_state = new_state
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.current_state}"


# -------------------------
# SYSTEM SETTINGS
# -------------------------
class SystemSettings(models.Model):
    institution_name = models.CharField(max_length=200, default="Ardhi University")
    system_name = models.CharField(max_length=100, default="GeoAttend")
    timezone = models.CharField(max_length=100, default="Africa/Dar_es_Salaam")

    late_threshold_minutes = models.PositiveIntegerField(default=30)
    minimum_attendance_percentage = models.PositiveIntegerField(default=75)
    checkout_grace_period_minutes = models.PositiveIntegerField(default=10)

    default_geofence_radius_meters = models.PositiveIntegerField(default=20)
    require_location_verification = models.BooleanField(default=True)

    require_wifi_verification = models.BooleanField(default=True)
    require_ble_verification = models.BooleanField(default=True)
    require_fingerprint_verification = models.BooleanField(default=True)
    require_otp_verification = models.BooleanField(default=True)

    notifications_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.institution_name} - System Settings"
