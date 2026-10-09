from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from students.models import Student, Notification
from django.db.models import Count, Q


from students.serializers import NotificationSerializer
from academic_calendar.models import SemesterCalendar

from accounts.models import UserSessionState
from accounts.permissions import IsLecturer, IsStudent

from courses.models import (
    Subject,
    Timetable,
    LecturerCourse,
    LecturerSubject,
    Classroom
)


from .models import AttendanceSession, Attendance, MovementLog,  SessionChangeHistory
from .utils import calculate_distance



def is_within_geofence(distance, radius):
    return distance <= radius


MOVEMENT_SAMPLE_MAX_GAP_SECONDS = 30


def calculate_movement_attendance(attendance):
    """
    Calculate verified attendance from consecutive movement samples.

    Only intervals with two inside-geofence samples are counted.
    Long gaps and time outside the actual session are not counted.
    """
    if not attendance.check_in_time:
        return {
            "attended_seconds": 0,
            "percentage": 0.0,
        }

    session = attendance.session

    if not session.start_time or not session.end_time:
        return {
            "attended_seconds": 0,
            "percentage": 0.0,
        }

    session_start = session.start_time
    session_end = session.end_time

    # Never count time outside the real session or the student's
    # own check-in/check-out window.
    window_start = max(attendance.check_in_time, session_start)
    window_end = min(
        attendance.check_out_time or timezone.now(),
        session_end,
    )

    if window_end <= window_start:
        return {
            "attended_seconds": 0,
            "percentage": 0.0,
        }

    logs = list(
        MovementLog.objects.filter(
            student=attendance.student,
            session=session,
            timestamp__gte=window_start,
            timestamp__lte=window_end,
        ).order_by("timestamp", "id")
    )

    attended_seconds = 0

    for previous, current in zip(logs, logs[1:]):
        if not previous.inside_geofence or not current.inside_geofence:
            continue

        gap_seconds = (
            current.timestamp - previous.timestamp
        ).total_seconds()

        if gap_seconds <= 0:
            continue

        if gap_seconds > MOVEMENT_SAMPLE_MAX_GAP_SECONDS:
            continue

        attended_seconds += gap_seconds

    scheduled_seconds = (
        session_end - session_start
    ).total_seconds()

    percentage = (
        min(attended_seconds / scheduled_seconds * 100, 100.0)
        if scheduled_seconds > 0
        else 0.0
    )

    return {
        "attended_seconds": attended_seconds,
        "percentage": round(percentage, 2),
    }

# ======================================================
# ACTIVE CLASS CHECK
# ======================================================

def get_active_class():

    now = timezone.localtime()

    days = {
        0: "MON",
        1: "TUE",
        2: "WED",
        3: "THU",
        4: "FRI",
        5: "SAT",
        6: "SUN",
    }

    return Timetable.objects.filter(
        day=days[now.weekday()],
        start_time__lte=now.time(),
        end_time__gte=now.time()
    ).first()



# ======================================================
# START ATTENDANCE SESSION
# LECTURER
# ======================================================

@api_view(["POST"])
@permission_classes([IsLecturer])
def start_session(request):

    existing_session = AttendanceSession.objects.filter(
    lecturer=request.user,
    is_active=True
    ).first()


    if existing_session:

        return Response(
        {
            "error":
            "You already have an active session. End it before starting another one."
        },
        status=400
    )

    user = request.user

    course_id = request.data.get("course_id")
    subject_id = request.data.get("subject_id")
    classroom_id = request.data.get("classroom_id")
    is_override = request.data.get(
        "is_override",
         False
    )

    override_reason = request.data.get(
        "override_reason"
    )
    override_start_time = request.data.get(
    "override_start_time"
    )

    override_end_time = request.data.get(
    "override_end_time"
    )


    # ==============================
# CHECK TIMETABLE
# ==============================

    days = {
    0: "MON",
    1: "TUE",
    2: "WED",
    3: "THU",
    4: "FRI",
    5: "SAT",
    6: "SUN",
    }


    today = timezone.localtime().weekday()


    timetable = Timetable.objects.filter(
    course_id=course_id,
    subject_id=subject_id,
    lecturer=user,
    day=days[today]
    ).first()


    if not timetable and not is_override:

        return Response(
            {
                "error": "No timetable found. Use override with reason if this is a postponed/replacement class."
            },
            status=400
        )

    # Reject normal sessions outside the scheduled timetable period.
    now = timezone.localtime()
    current_time = now.time()

    if timetable and not is_override:
        if not (timetable.start_time <= current_time < timetable.end_time):
            return Response(
                {
                    "error": (
                        f"This class is scheduled from "
                        f"{timetable.start_time.strftime('%H:%M')} to "
                        f"{timetable.end_time.strftime('%H:%M')}. "
                        "You cannot start attendance outside this period."
                    )
                },
                status=400
            )

    if is_override and not override_reason:

        return Response(
            {
                "error": "Override reason is required"
            },
            status=400
        )

    if is_override and (
        not override_start_time or
        not override_end_time
    ):

        return Response(
            {
                "error": "Override start time and end time are required"
            },
            status=400
        )

    # Fixed, explicit values for the current demo environment.
    allowed_wifi = "ARUSOPASUANET"

    if not course_id or not subject_id:
        return Response(
            {
                "error": "course_id and subject_id are required"
            },
            status=400
        )

    if not classroom_id:
        return Response(
            {
                "error": "classroom_id is required"
            },
            status=400
        )

    classroom = Classroom.objects.filter(
        id=classroom_id
    ).first()

    if not classroom:
        return Response(
            {
                "error": "Invalid classroom"
            },
            status=400
        )


    # Lecturer course permission

    if not user.is_staff and not user.is_superuser:

        allowed_course = LecturerCourse.objects.filter(
            lecturer=user,
            course_id=course_id
        ).exists()

        if not allowed_course:
            return Response(
                {
                    "error": "You are not assigned to this course"
                },
                status=403
            )


    # Validate subject

    subject = Subject.objects.filter(
        id=subject_id,
        course_id=course_id
    ).first()


    if not subject:
        return Response(
            {
                "error": "Invalid subject"
            },
            status=400
        )


    # Lecturer subject permission

    if not user.is_staff and not user.is_superuser:

        allowed_subject = LecturerSubject.objects.filter(
            lecturer=user,
            subject=subject
        ).exists()


        if not allowed_subject:
            return Response(
                {
                    "error": "You are not allowed to teach this subject"
                },
                status=403
            )

    now = timezone.localtime()

        # ==========================================
    # AMENDMENT 4: DAILY SESSION TIME RESTRICTION
    # ==========================================

    current_time = now.time()

    allowed_start = datetime.strptime(
        "07:00",
        "%H:%M"
    ).time()

    allowed_end = datetime.strptime(
        "20:00",
        "%H:%M"
    ).time()

    if current_time < allowed_start or current_time > allowed_end:
        return Response(
            {
                "error": (
                    "Attendance sessions can only be started "
                    "between 07:00 and 20:00."
                )
            },
            status=400
        )



    if is_override:

        try:
            override_start = datetime.strptime(
                override_start_time,
                "%H:%M"
            ).time()

            override_end = datetime.strptime(
                override_end_time,
                "%H:%M"
            ).time()

        except (TypeError, ValueError):

            return Response(
                {
                    "error": "Override times must use HH:MM format, for example 09:00"
                },
                status=400
            )

                # ==========================================
        # AMENDMENT 4: OVERRIDE TIME RESTRICTION
        # ==========================================

        if (
            override_start < allowed_start
            or override_end > allowed_end
        ):
            return Response(
                {
                    "error": (
                        "Override sessions must start and end "
                        "between 07:00 and 20:00."
                    )
                },
                status=400
            )

        if override_end <= override_start:

            return Response(
                {
                    "error": "Override end time must be after start time"
                },
                status=400
            )
        if not (override_start <= current_time < override_end):
            return Response(
           {
            "error": (
                "The current time is outside the approved override "
                "period. Attendance cannot be started."
            )
            },
        status=400
    )

        session_start_time = timezone.make_aware(
            datetime.combine(
                now.date(),
                override_start
            ),
            timezone.get_current_timezone()
        )

        session_end_time = timezone.make_aware(
            datetime.combine(
                now.date(),
                override_end
            ),
            timezone.get_current_timezone()
        )
        if session_end_time <= now:
            return Response(
        {
            "error": (
                "The override end time has already passed. "
                "Choose a future end time."
            )
        },
        status=400
    )


    else:
        session_start_time = now

        session_end_time = timezone.make_aware(
            datetime.combine(
                now.date(),
                timetable.end_time
            ),
            timezone.get_current_timezone()
        )

        # Normal timetable session cannot start after
        # its scheduled end time.
        if session_end_time <= now:
            return Response(
                {
                    "error": (
                        "This timetable session has already ended. "
                        "Use override if this is a postponed or "
                        "replacement class."
                    )
                },
                status=400
            )


    if timetable:
        scheduled_start_time = timezone.make_aware(
            datetime.combine(
                now.date(),
                timetable.start_time
            ),
            timezone.get_current_timezone()
        )

        scheduled_end_time = timezone.make_aware(
            datetime.combine(
                now.date(),
                timetable.end_time
            ),
            timezone.get_current_timezone()
        )
    else:
        scheduled_start_time = session_start_time
        scheduled_end_time = session_end_time

    session = AttendanceSession.objects.create(
        lecturer=user,
        course_id=course_id,
        subject=subject,
        classroom=classroom,
        timetable=timetable,
        latitude=classroom.latitude,
        longitude=classroom.longitude,
        radius_meters=classroom.radius_meters,
        allowed_wifi_bssid=allowed_wifi,
        start_time=session_start_time,
        end_time=session_end_time,
        is_active=(
            session_start_time <= now
        ),
        is_override=is_override,
        override_reason=override_reason,
        override_duration_minutes=120
    )

    SessionChangeHistory.objects.create(
        session=session,
        change_type=(
            "OVERRIDE_STARTED"
            if is_override
            else "SESSION_STARTED"
        ),
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        actual_start_time=session.start_time,
        actual_end_time=session.end_time,
        changed_by=user,
        reason=(
            override_reason or ""
            if is_override
            else ""
        ),
    )
    students = Student.objects.filter(
        course=session.course
    )

    for student in students:

        if session.is_active:

            Notification.objects.create(
                student=student,
                title="Attendance Session Started",
                message=(
                    f"{session.subject.name} session is now active."
                )
            )

        else:

            Notification.objects.create(
                student=student,
                title="Attendance Session Scheduled",
                message=(
                    f"{session.subject.name} session is scheduled "
                    f"to start at "
                    f"{session.start_time.strftime('%H:%M')}."
                )
            )

    return Response(
        {
            "message": "Session started successfully",
            "session_id": session.id
        },
        status=201
    )



# ======================================================
# STUDENT CHECK IN
# ======================================================

@api_view(["POST"])
@permission_classes([IsStudent])
def check_in(request):

    user = request.user


    session_id = request.data.get("session_id")

    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")
    wifi_bssid = request.data.get("wifi_bssid")
    beacon_id = request.data.get("beacon_id")


    if not session_id:
        return Response(
            {
                "error": "session_id required"
            },
            status=400
        )


    try:

        student = user.student

    except Student.DoesNotExist:

        return Response(
            {
                "error": "Student profile not found"
            },
            status=404
        )



    session = AttendanceSession.objects.filter(
    id=session_id,
    is_active=True
).first()


    if not session:
        return Response(
        {
            "error": "Active session not found"
        },
        status=404
    )




    state, _ = UserSessionState.objects.get_or_create(
    user=user
    )



    # GPS validation

    distance = calculate_distance(

        latitude,

        longitude,

        session.latitude,

        session.longitude

    )


    if distance > session.radius_meters:

        return Response(
            {
                "error": "Outside attendance location"
            },
            status=403
        )

    # WiFi and BLE are checked before identity verification. Keep this order
    # consistent with the Flutter validation flow.
    if session.allowed_wifi_bssid and wifi_bssid != session.allowed_wifi_bssid:
        return Response({"error": "Unauthorized WiFi network"}, status=403)

    # BLE classroom validation
    if not session.classroom:
        return Response(
        {
            "error": "No classroom configured for this session"
        },
        status=403
    )

    expected_beacon = getattr(session.classroom, "beacon", None)

    if not expected_beacon:
        return Response(
        {
            "error": "No BLE beacon assigned to this classroom"
        },
        status=403
    )

    if beacon_id != expected_beacon.beacon_id:
        return Response(
        {
            "error": "Wrong classroom BLE beacon detected"
        },
        status=403
    )

        # fingerprint verification

    if state.current_state != "ATTENDANCE_GRANTED":

        return Response(
            {
                "error": "Fingerprint verification required",
                "state": state.current_state
            },
            status=403
        )

    attendance, created = Attendance.objects.get_or_create(
    student=student,
    session=session,
    defaults={
        "status": "PRESENT",
        "check_in_time": timezone.now()
    }
)


    if not created:

        if attendance.check_in_time:
            return Response(
              {
                "error": "Already checked in"
            },
            status=400
            )

    # Update existing ABSENT record

    attendance.status = "PRESENT"
    attendance.check_in_time = timezone.now()
    attendance.save()

# Record the student's initial verified location at check-in.
    MovementLog.objects.create(
    student=student,
    session=session,
    latitude=float(latitude),
    longitude=float(longitude),
    inside_geofence=True,
)



    state.current_state = "CHECKED_IN"
    state.save()

    Notification.objects.create(
    student=student,
    title="Check-in successful",
    message=f"You checked into {session.subject.name}"
)









    return Response(
        {
            "message": "Checked-in successfully",

            "attendance_id": attendance.id,

            "status": attendance.status,

            "distance": round(distance,2)
        }
    )




# ======================================================
# STUDENT CHECK OUT
# ======================================================

@api_view(["POST"])
@permission_classes([IsStudent])
def check_out(request):

    user = request.user

    session_id = request.data.get("session_id")

    latitude = request.data.get("latitude")
    longitude = request.data.get("longitude")

    wifi_bssid = request.data.get("wifi_bssid")
    beacon_id = request.data.get("beacon_id")


    try:

        student = user.student

    except Student.DoesNotExist:

        return Response(
            {
                "error": "Student profile not found"
            },
            status=404
        )



    attendance = Attendance.objects.filter(

        student=student,

        session_id=session_id,

        check_out_time__isnull=True

    ).first()



    if not attendance:

        return Response(
            {
                "error": "No active attendance record found"
            },
            status=404
        )



    session = attendance.session

    if not session:
        return Response(
        {
            "error":"Session not found"
        },
        status=404
    )



    # Session must end before checkout

    if session.is_active:

        return Response(
            {
                "error": "Session is still active. Checkout is allowed after lecturer ends the session."
            },
            status=403
        )

    if session.checkout_deadline and timezone.now() > session.checkout_deadline:

        return Response(
        {
            "error":
            "Checkout period expired. You can no longer checkout."
        },
        status=403
        )



    # GPS validation

    distance = calculate_distance(

        latitude,

        longitude,

        session.latitude,

        session.longitude

    )


    if distance > session.radius_meters:

        return Response(
            {
                "error": "Outside allowed attendance area"
            },
            status=403
        )



    # WIFI validation

    if session.allowed_wifi_bssid:

        if wifi_bssid != session.allowed_wifi_bssid:

            return Response(
                {
                    "error": "Unauthorized WiFi network"
                },
                status=403
            )



    # BLE classroom validation

    if not session.classroom:
        return Response(
        {
            "error": "No classroom beacon configured for this session"
        },
        status=403
    )


    expected_beacon = session.classroom.beacon


    if not expected_beacon:
        return Response(
        {
            "error": "No BLE beacon assigned to this classroom"
        },
        status=403
    )


    if beacon_id != expected_beacon.beacon_id:
        return Response(
        {
            "error": "Wrong classroom BLE beacon detected"
        },
        status=403
    )


    state, _ = UserSessionState.objects.get_or_create(
    user=user
)


    if state.current_state not in [
    "ATTENDANCE_GRANTED",
    "CHECKED_IN"
    ]:
        return Response(
        {
            "error": "Fingerprint verification required",
            "state": state.current_state
        },
        status=403
    )

    checkout_time = timezone.now()

# Save checkout time before calculating attendance.
    attendance.check_out_time = checkout_time

# Calculate attendance using verified movement samples,
# not simply the time between check-in and checkout.
    movement_result = calculate_movement_attendance(attendance)

    attendance.attendance_percentage = movement_result["percentage"]

    if attendance.attendance_percentage < 80:
       attendance.status = "PARTIAL_ATTENDANCE"
    else:
       attendance.status = calculate_attendance_status(attendance)

    attendance.save(
    update_fields=[
        "check_out_time",
        "attendance_percentage",
        "status",
    ]
)



    percentage = attendance.attendance_percentage or 0

    # Notification must not prevent checkout from succeeding.
    try:
        Notification.objects.create(
        student=student,
        title="Checkout successful",
        message=f"Attendance completed with {percentage:.0f}% attendance."
    )
    except Exception as notification_error:
       print("CHECKOUT NOTIFICATION ERROR:", notification_error)

    state.current_state = "IDLE"
    state.save()



    return Response(
        {
            "message": "Checked-out successfully",

            "status": attendance.status,

            "check_out_time": checkout_time,

            "attendance_percentage":
                attendance.attendance_percentage
        }
    )





# ======================================================
# END SESSION
# LECTURER
# ======================================================

@api_view(["POST"])
@permission_classes([IsLecturer])
def end_session(request):

    session = AttendanceSession.objects.filter(
        lecturer=request.user,
        is_active=True
    ).first()

    if not session:
        return Response(
            {
                "error": "No active session"
            },
            status=404
        )

    session.is_active = False

    session.end_time = timezone.now()

    session.ended_at = timezone.now()

    session.checkout_deadline = (
    session.end_time + timedelta(minutes=10)
    )

    session.save()



    students = Student.objects.filter(
        course=session.course
    )


    # Create ABSENT records for students who never checked in
    for student in students:

        Attendance.objects.get_or_create(
            student=student,
            session=session,
            defaults={
                "status": "ABSENT",
                "attendance_percentage": 0
            }
        )


    # Notify all students
    for student in students:

        Notification.objects.create(
            student=student,
            title="Session ended",
            message=f"{session.subject.name} session has ended."
        )


    return Response(
        {
            "message": "Session ended successfully",
            "session_id": session.id
        }
    )
# ======================================================
# LECTURER DASHBOARD
# ======================================================

@api_view(["GET"])
@permission_classes([IsLecturer])
def lecturer_dashboard(request):

    sessions = AttendanceSession.objects.filter(
        lecturer=request.user
    ).order_by("-start_time")


    data = []


    for session in sessions:


        records = Attendance.objects.filter(
            session=session
        )


        total = records.count()

        present = records.filter(
            status="PRESENT"
        ).count()

        late = records.filter(
            status="LATE"
        ).count()

        absent = records.filter(
            status="ABSENT"
        ).count()



        percentage = (

            present / total * 100

        ) if total else 0



        data.append({

            "session_id": session.id,

            "course": session.course.name,

            "subject": session.subject.name,

            "date": session.date,

            "active": session.is_active,

            "total_students": total,

            "present": present,

            "late": late,

            "absent": absent,

            "percentage": round(
                percentage,
                2
            )

        })



    return Response(
        {
            "sessions": data
        }
    )





# ======================================================
# ATTENDANCE REPORT
# ======================================================

@api_view(["GET"])
@permission_classes([IsLecturer])
def attendance_report(request):

    sessions = AttendanceSession.objects.filter(
        lecturer=request.user
    ).order_by("-start_time")


    result = []


    for session in sessions:


        records = Attendance.objects.filter(
            session=session
        )


        total = records.count()


        present = records.filter(
            status="PRESENT"
        ).count()



        result.append({

            "session_id": session.id,

            "course": session.course.name,

            "subject": session.subject.name,

            "total": total,

            "present": present,

            "absent":
                records.filter(
                    status="ABSENT"
                ).count(),

            "percentage":
                round(
                    (present / total) * 100,
                    2
                )
                if total else 0

        })


    return Response(
        {
            "sessions": result
        }
    )





# ======================================================
# SINGLE SESSION REPORT
# ======================================================

@api_view(["GET"])
@permission_classes([IsLecturer])
def session_report(request, session_id):


    if not session_id:
        return Response(
        {
            "error": "session_id is required"
        },
        status=400
        )

    session = AttendanceSession.objects.filter(
    id=session_id,
    lecturer=request.user
).first()

    if not session:
        return Response(
        {
            "error": "Session not found"
        },
        status=404
        )



    records = Attendance.objects.filter(
        session=session
    ).select_related(
        "student"
    )



    return Response({

        "session_id": session.id,

        "course": session.course.name,

        "subject": session.subject.name,


        "records": [

            {

                "student_id": record.student.id,

                "name": record.student.full_name,

                "registration":
                    record.student.reg_number,

                "status": record.status,

                "check_in":
                    record.check_in_time,

                "check_out":
                    record.check_out_time

            }

            for record in records

        ]

    })





# ======================================================
# STUDENT ACTIVE SESSION
# ======================================================
@api_view(["GET"])
@permission_classes([IsStudent])
def active_session(request):

    auto_close_expired_sessions()

    try:
        student = request.user.student
    except Student.DoesNotExist:
        return Response(
            {"error": "Student profile not found"},
            status=404
        )

    now = timezone.localtime()

    # =========================================================
    # 1. FIND STUDENT'S OPEN ATTENDANCE
    # =========================================================

    attendance = (
        Attendance.objects.filter(
            student=student,
            check_in_time__isnull=False,
            check_out_time__isnull=True,
        )
        .select_related(
            "session",
            "session__course",
            "session__subject",
            "session__classroom",
        )
        .order_by("-check_in_time")
        .first()
    )

    if attendance:

        session = attendance.session

        # =====================================================
        # OLD SESSION: CHECKOUT DEADLINE STILL VALID
        # =====================================================

        if (
            not session.is_active
            and session.checkout_deadline
            and now <= session.checkout_deadline
        ):

            return Response({
                "session_exists": True,
                "session_id": session.id,

                "session_active": False,
                "session_ended": True,

                "start_time": (
                    session.start_time.isoformat()
                    if session.start_time else None
                ),

                "end_time": (
                    session.end_time.isoformat()
                    if session.end_time else None
                ),

                "checkout_deadline": (
                    session.checkout_deadline.isoformat()
                    if session.checkout_deadline else None
                ),

                "course": session.course.name,
                "subject": session.subject.name,

                "latitude": session.latitude,
                "longitude": session.longitude,
                "radius_meters": session.radius_meters,

                "attendance_state": "CHECKED_IN",

                "checked_in": True,
                "checked_out": False,

                "can_check_in": False,
                "can_check_out": True,

                "auto_closed": session.auto_closed,

                "beacon_id": (
                    session.classroom.beacon.beacon_id
                    if session.classroom
                    and hasattr(session.classroom, "beacon")
                    and session.classroom.beacon
                    else None
                ),
            })

        # =====================================================
        # OLD SESSION: CHECKOUT DEADLINE EXPIRED
        #
        # IMPORTANT:
        # DO NOT RETURN HERE.
        #
        # We continue below so a NEW active session can be found.
        # =====================================================

        if (
            not session.is_active
            and session.checkout_deadline
            and now > session.checkout_deadline
        ):

            # The old attendance is no longer an active
            # checkout opportunity.
            #
            # We deliberately do NOT return "session_exists=false"
            # because another newer attendance session may exist.

            pass

        # =====================================================
        # CURRENT SESSION STILL ACTIVE
        # =====================================================

        elif session.is_active:

            return Response({
                "session_exists": True,
                "session_id": session.id,

                "session_active": True,
                "session_ended": False,

                "start_time": (
                    session.start_time.isoformat()
                    if session.start_time else None
                ),

                "end_time": (
                    session.end_time.isoformat()
                    if session.end_time else None
                ),

                "checkout_deadline": (
                    session.checkout_deadline.isoformat()
                    if session.checkout_deadline else None
                ),

                "course": session.course.name,
                "subject": session.subject.name,

                "latitude": session.latitude,
                "longitude": session.longitude,
                "radius_meters": session.radius_meters,

                "attendance_state": "CHECKED_IN",

                "checked_in": True,
                "checked_out": False,

                "can_check_in": False,
                "can_check_out": False,

                "auto_closed": session.auto_closed,

                "beacon_id": (
                    session.classroom.beacon.beacon_id
                    if session.classroom
                    and hasattr(session.classroom, "beacon")
                    and session.classroom.beacon
                    else None
                ),
            })

    # =========================================================
    # 2. STUDENT ALREADY CHECKED OUT
    # =========================================================

    completed = (
        Attendance.objects.filter(
            student=student,
            check_in_time__isnull=False,
            check_out_time__isnull=False,
        )
        .select_related(
            "session",
            "session__course",
            "session__subject",
            "session__classroom",
        )
        .order_by("-check_out_time")
        .first()
    )

    # IMPORTANT:
    # Only return CHECKED_OUT if there isn't a newer active
    # session that the student needs to attend.
    #
    # Therefore we don't return immediately here.

    # =========================================================
    # 3. FIND CURRENT ACTIVE LECTURER SESSION
    # =========================================================

    session = (
        AttendanceSession.objects.filter(
            course=student.course,
            is_active=True,
        )
        .select_related(
            "course",
            "subject",
            "classroom",
        )
        .order_by("-start_time")
        .first()
    )

    if session:

        return Response({
            "session_exists": True,
            "session_id": session.id,

            "session_active": True,
            "session_ended": False,

            "start_time": (
                session.start_time.isoformat()
                if session.start_time else None
            ),

            "end_time": (
                session.end_time.isoformat()
                if session.end_time else None
            ),

            "checkout_deadline": (
                session.checkout_deadline.isoformat()
                if session.checkout_deadline else None
            ),

            "course": session.course.name,
            "subject": session.subject.name,

            "latitude": session.latitude,
            "longitude": session.longitude,
            "radius_meters": session.radius_meters,

            "attendance_state": "NOT_CHECKED_IN",

            "checked_in": False,
            "checked_out": False,

            "can_check_in": True,
            "can_check_out": False,

            "auto_closed": session.auto_closed,

            "beacon_id": (
                session.classroom.beacon.beacon_id
                if session.classroom
                and hasattr(session.classroom, "beacon")
                and session.classroom.beacon
                else None
            ),
        })

    # =========================================================
    # 4. NO ACTIVE SESSION
    # =========================================================

    if completed:

        return Response({
        "session_exists": False,

        "attendance_state": "CHECKED_OUT",

        "checked_in": False,
        "checked_out": True,

        "can_check_in": False,
        "can_check_out": False,

        "percentage": completed.attendance_percentage,

        "message": "Attendance already completed"
    })

    return Response({
        "session_exists": False,
        "attendance_state": "NOT_CHECKED_IN",
        "checked_in": False,
        "checked_out": False,
        "can_check_in": False,
        "can_check_out": False,
        "message": "No active attendance session available",
    })

def auto_close_expired_sessions():

    now = timezone.localtime()

    # ==========================================
    # ACTIVATE SCHEDULED SESSIONS
    # ==========================================

    scheduled_sessions = AttendanceSession.objects.filter(
        is_active=False,
        start_time__lte=now,
        end_time__gt=now
    )

    for session in scheduled_sessions:

        session.is_active = True

        session.save(
            update_fields=["is_active"]
        )


    # ==========================================
    # AUTO-CLOSE ACTIVE SESSIONS
    # ==========================================

    active_sessions = AttendanceSession.objects.filter(
        is_active=True
    )

    for session in active_sessions:

        # AttendanceSession.end_time is the
        # source of truth for BOTH normal
        # and override sessions.

        session_end = session.end_time

        if not session_end:
            continue


        # Safety check:
        # never process a session before
        # its scheduled start time.

        if now < session.start_time:
            continue


        # ==========================================
        # AUTO CLOSE
        # ==========================================

        if now >= session_end:

            session.is_active = False

            session.ended_at = now

            session.auto_closed = True

            session.checkout_deadline = (
                now + timedelta(minutes=10)
            )

            session.save()


            students = Student.objects.filter(
                course=session.course
            )


            for student in students:

                Notification.objects.create(
                    student=student,
                    title="Session automatically ended",
                    message=(
                        f"{session.subject.name} session "
                        "was automatically closed. "
                        "Checkout is available for 10 minutes."
                    )
                )



    # ==========================================
    # AUTO-CLOSE STUDENTS WHO NEVER CHECKED OUT
    # ==========================================

    expired_sessions = AttendanceSession.objects.filter(
        is_active=False,
        checkout_deadline__lt=now,
    )

    for session in expired_sessions:
        open_attendance = Attendance.objects.filter(
            session=session,
            check_in_time__isnull=False,
            check_out_time__isnull=True,
        )

        for attendance in open_attendance:
            # Stop attendance at the actual session end.
            attendance.check_out_time = session.end_time

            # Use the same movement-based calculation as normal checkout.
            movement_result = calculate_movement_attendance(
                attendance
            )

            attendance.attendance_percentage = (
                movement_result["percentage"]
            )

            attendance.status = calculate_attendance_status(
                attendance
            )

            attendance.save(
                update_fields=[
                    "check_out_time",
                    "attendance_percentage",
                    "status",
                ]
            )

# ======================================================
# ATTENDANCE STATUS CALCULATION
# ======================================================

def calculate_attendance_status(attendance):
    if not attendance.check_in_time:
        return "ABSENT"

    # Attendance below 80% is always partial.
    if (attendance.attendance_percentage or 0) < 80:
        return "PARTIAL_ATTENDANCE"

    session_start = attendance.session.start_time if attendance.session else None

    if session_start:
        grace_time = session_start + timedelta(minutes=30)

        if attendance.check_in_time > grace_time:
            return "LATE"

    return "PRESENT"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def location_update(request):
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        return Response(
            {"error": "Student profile not found"},
            status=404
        )

    # Validate GPS coordinates before calculating distance.
    try:
        latitude = float(request.data.get("latitude"))
        longitude = float(request.data.get("longitude"))
    except (TypeError, ValueError):
        return Response(
            {"error": "Valid latitude and longitude are required"},
            status=400
        )

    import math

    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return Response(
            {"error": "GPS coordinates are invalid"},
            status=400
        )

    attendance = (
        Attendance.objects
        .filter(
            student=student,
            check_in_time__isnull=False,
            check_out_time__isnull=True,
        )
        .select_related("session")
        .order_by("-check_in_time")
        .first()
    )

    if not attendance:
        return Response(
            {"message": "No open attendance record"},
            status=400
        )

    session = attendance.session
    now = timezone.now()

    # Never record movement after the actual session end.
    if not session.end_time or now >= session.end_time:
        return Response(
            {"error": "The session has ended. Movement recording is closed."},
            status=403
        )

    distance = calculate_distance(
        latitude,
        longitude,
        session.latitude,
        session.longitude
    )

    inside_geofence = distance <= session.radius_meters

    # Store the GPS evidence. The server determines geofence status.
    # Wi-Fi/beacon flags are retained for compatibility but are not
    # considered proof of attendance by the scoring helper.
    MovementLog.objects.create(
        student=student,
        session=session,
        latitude=latitude,
        longitude=longitude,
        inside_geofence=inside_geofence,
        wifi_valid=request.data.get("wifi_valid", False),
        beacon_valid=request.data.get("beacon_valid", False)
    )

    return Response({
        "message": "Movement recorded",
        "inside_geofence": inside_geofence,
        "distance_meters": round(distance, 2),
    })


@api_view(['GET'])
def student_attendance_history(request):
    user = request.user
    student = Student.objects.get(user=user)

    # Get this student's attendance records
    attendance_records = Attendance.objects.filter(
        student=student
    ).select_related(
        "session",
        "session__subject",
        "session__course",
        "session__timetable",
    ).order_by(
        "session__date",
        "session__start_time",
    )


    def get_scheduled_hours(session):
        """
        Return the scheduled duration in hours.

        Override sessions use their configured duration.
        Normal sessions use their timetable duration.
        Actual session times are a fallback only.
        """

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

        # Fallback when timetable information is unavailable.
        if session.start_time and session.end_time:
            duration = (
                session.end_time - session.start_time
            ).total_seconds() / 3600

            return max(duration, 0)

        return 0

    def get_attended_hours(attendance):
        """
        Return verified movement-based attendance hours
        for an individual session.
        """

        if not attendance.check_in_time:
            return 0

        movement_result = calculate_movement_attendance(attendance)
        attended_seconds = movement_result["attended_seconds"]

        return max(attended_seconds / 3600, 0)


    def calculate_subject_percentage(subject, current_session):
        """
        Calculate subject attendance using eligible timetable hours
        within the saved semester teaching period.

        For testing sessions outside the teaching period, retain the
        existing session-based calculation.
        """

        subject_records = attendance_records.filter(
            session__subject=subject,
            session__date__lte=current_session.date,
        )

        def legacy_percentage():
            total_scheduled = 0
            total_attended = 0

            for record in subject_records:
                scheduled = get_scheduled_hours(record.session)
                attended = get_attended_hours(record)

                total_scheduled += scheduled
                total_attended += min(attended, scheduled)

            if total_scheduled <= 0:
                return 0

            return round(
                min(total_attended / total_scheduled * 100, 100),
                2,
            )

        calendar = None

        if current_session.date:
            calendar = SemesterCalendar.objects.filter(
                teaching_start_date__isnull=False,
                teaching_end_date__isnull=False,
                teaching_start_date__lte=current_session.date,
                teaching_end_date__gte=current_session.date,
            ).first()

            # Preserve the existing calculation if no usable calendar
            # exists or this is a testing session outside the teaching dates.
            if (
                not calendar
                or not current_session.date
                or current_session.date < calendar.teaching_start_date
            ):
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

            # If no matching timetable exists, retain the old calculation
            # rather than incorrectly returning zero.
            if not timetables.exists():
                return legacy_percentage()

            total_scheduled_hours = 0
            total_attended_hours = 0

            # Generate eligible scheduled hours from recurring timetable
            # entries, from the teaching start through the current session.
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

                        duration_hours = (
                            end_minutes - start_minutes
                        ) / 60

                        total_scheduled_hours += duration_hours

                scheduled_date += timedelta(days=1)

            # Count attended time only for records on eligible teaching dates.
            for record in subject_records:
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

                scheduled_hours = get_scheduled_hours(record.session)
                attended_hours = get_attended_hours(record)

                total_attended_hours += min(
                    attended_hours,
                    scheduled_hours,
                )

            if total_scheduled_hours <= 0:
                return legacy_percentage()

            percentage = (
                total_attended_hours / total_scheduled_hours
            ) * 100

            return round(min(percentage, 100), 2)

        return legacy_percentage()

    # ---------------------------------------------------------
    # CURRENT OVERALL ATTENDANCE
    # ---------------------------------------------------------

    total_sessions = attendance_records.count()

    overall_percentage = 0

    if total_sessions > 0:
        total_percentage = sum(
            float(record.attendance_percentage or 0)
            for record in attendance_records
        )

        overall_percentage = total_percentage / total_sessions

    # ---------------------------------------------------------
    # SUBJECT PERFORMANCE
    # ---------------------------------------------------------

    subjects = Subject.objects.filter(
        course=student.course
    )

    subject_performance = []

    for subject in subjects:
        subject_records = attendance_records.filter(
            session__subject=subject
        )

        if subject_records.exists():
            latest_session = subject_records.order_by(
                "-session__date",
                "-session__start_time",
            ).first().session

            percentage = calculate_subject_percentage(
                subject,
                latest_session
            )
        else:
            percentage = 0

        subject_performance.append({
            "subject": subject.name,
            "percentage": percentage,
        })

    # ---------------------------------------------------------
    # ATTENDANCE HISTORY
    # ---------------------------------------------------------

    history = []

    for record in attendance_records:

        session = record.session

        subject_percentage = calculate_subject_percentage(
            session.subject,
            session
        )

        history.append({
            "id": record.id,

            "subject": session.subject.name,

            "course": session.course.name,

            # Date of the attendance session
            "date": session.date.isoformat()
            if session.date else None,

            "check_in_time": (
                record.check_in_time.isoformat()
                if record.check_in_time
                else None
            ),

            "check_out_time": (
                record.check_out_time.isoformat()
                if record.check_out_time
                else None
            ),

            # Attendance percentage for THIS session
            "attendance_percentage": float(
                record.attendance_percentage or 0
            ),

            "status": record.status,

            # Cumulative attendance for THIS subject
            "subject_attendance_percentage": subject_percentage,
        })

    return Response({
        "overall_percentage": round(
            overall_percentage,
            2
        ),

        "total_sessions": total_sessions,

        "subject_performance": subject_performance,

        "history": history,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications(request):

    student = Student.objects.filter(
        user=request.user
    ).first()

    if not student:
        return Response(
            {
                "error": "Student not found"
            },
            status=404
        )

    notification_list = Notification.objects.filter(
        student=student
    ).order_by("-created_at")

    serializer = NotificationSerializer(
    notification_list,
    many=True
)

    unread_count = notification_list.filter(
    is_read=False
    ).count()

    return Response({
    "unread_count": unread_count,
    "notifications": serializer.data,
})
