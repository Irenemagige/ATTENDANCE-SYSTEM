from django.urls import path
from .admin_report_views import admin_report_preview, admin_report_filters, admin_report_export
from .views import start_session
from .admin_dashboard_views import admin_dashboard

from .hod_views import hod_dashboard, hod_students, hod_analytics
from .hod_report_views import hod_reports
from .hod_activity_views import hod_audit_history, hod_department_timetable

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
    path('admin/reports/', admin_report_preview, name='admin_report_preview'),
    path('admin/reports/filters/', admin_report_filters, name='admin_report_filters'),
    path('admin/reports/export/', admin_report_export, name='admin_report_export'),
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),

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
    
    # HOD department dashboard
    path(
    'hod/dashboard/',
    hod_dashboard,
    name='hod_dashboard',
),
    path('hod/students/', hod_students, name='hod_students'),
    path('hod/analytics/', hod_analytics, name='hod_analytics'),
    path('hod/reports/', hod_reports, name='hod_reports'),
    path('hod/activity-history/', hod_audit_history, name='hod_activity_history'),
    path('hod/timetable/', hod_department_timetable, name='hod_department_timetable'),
    path(
    'lecturer/active-session-monitor/',
    lecturer_active_session_monitor,
    name='lecturer_active_session_monitor',
),
]



