from django.urls import path
from .views import start_session

from .views import (
    start_session,
    check_in,
    check_out,
    end_session,
    lecturer_dashboard,
    lecturer_active_session_monitor,
    attendance_report,
    session_report,
    lecturer_attendance_history,
    active_session,
    location_update,
    notifications,
    student_attendance_history
)

urlpatterns = [
    # Lecturer session control
    path('start-session/', start_session, name='start_session'),
    path('start/', start_session, name='attendance_start'),
    path('end-session/', end_session, name='end_session'),
    path('end/', end_session, name='attendance_end'),


    # Student attendance
    path('check-in/', check_in, name='check_in'),
    path('check-out/', check_out, name='check_out'),
    path('active-session/', active_session, name='active_session'),
    path('location-update/', location_update, name='location-update'),
    path('history/',student_attendance_history, name='student_attendance_history'),

    # Lecturer dashboard
    path('lecturer/dashboard/', lecturer_dashboard, name='lecturer_dashboard'),
    path('report/', attendance_report, name='attendance_report'),
    path('session-report/<int:session_id>/', session_report, name='session_report'),
    path('notifications/', notifications, name='notifications'),
    path(
    'lecturer/attendance-history/',
    lecturer_attendance_history,
    name='lecturer_attendance_history',
),
    
    path(
    'lecturer/active-session-monitor/',
    lecturer_active_session_monitor,
    name='lecturer_active_session_monitor',
),
]


