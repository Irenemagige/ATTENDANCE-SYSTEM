from datetime import timedelta
from django.utils import timezone
from math import radians, sin, cos, sqrt, atan2

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def check_session_expiry(session):
    now = timezone.now()

    expected_end = session.start_time + timedelta(minutes=session.duration_minutes)

    if now >= expected_end and session.is_active:
        session.is_active = False
        session.end_time = expected_end
        session.save()

def calculate_attendance(attendance, session):

    if not attendance.check_out_time:
        return

    total = session.duration_minutes * 60

    spent = (attendance.check_out_time - attendance.check_in_time).seconds

    percent = (spent / total) * 100

    attendance.percentage = percent

    if percent >= 50:
        attendance.status = "Present"
    elif percent <= 50:
        attendance.status = "Late"
    else:
        attendance.status = "Absent"

    attendance.save()