from courses import timetable_import
from django.urls import path
from .views import assign_student_to_course, assign_lecturer_to_course
from . import views
from . import timetable_pdf

urlpatterns = [
    path('timetable/import/preview/', timetable_import.preview_timetable_import, name='preview-timetable-import'),
    path('timetable/import/confirm/', timetable_import.confirm_timetable_import, name='confirm-timetable-import'),
    path('timetable/pdf/preview/', timetable_pdf.preview_timetable_pdf, name='preview-timetable-pdf'),
    path('timetable/pdf/confirm/', timetable_pdf.confirm_timetable_pdf, name='confirm-timetable-pdf'),
    path('assign-student/', assign_student_to_course, name='assign_student_to_course'),
    path('assign-lecturer/', assign_lecturer_to_course, name='assign_lecturer-to_course'),
    path('lecturer/', views.lecturer_courses, name='lecturer_courses'),
    path('lecturer/timetable/', views.lecturer_timetable, name='lecturer_timetable'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('classrooms/', views.classroom_list, name='classroom_list'),
    path('timetable/admin/', views.admin_timetable_list, name='admin-timetable-list'),
    path('timetable/admin/options/', views.admin_timetable_options, name='admin-timetable-options'),
    path('timetable/admin/<int:pk>/', views.admin_timetable_detail, name='admin-timetable-detail'),
    path('timetable/create/', views.create_timetable, name='create_timetable'),
    path('timetable/upload/', views.upload_timetable_excel, name='upload_timetable_excel'),
    path('timetable/my/', views.my_timetable, name='my_timetable'),
    path('', views.course_list, name='course_list'),
    path('create/', views.course_create, name='course_create'),

    # Admin Academic Management
    path('admin/academic/options/', views.admin_academic_options, name='admin-academic-options'),
    path('admin/academic/courses/<int:pk>/', views.admin_course_detail, name='admin-course-detail'),
    path('admin/academic/subjects/', views.admin_subject_list_create, name='admin-subject-list-create'),
    path('admin/academic/subjects/<int:pk>/', views.admin_subject_detail, name='admin-subject-detail'),
    path('admin/academic/classrooms/', views.admin_classroom_list_create, name='admin-classroom-list-create'),
    path('admin/academic/classrooms/<int:pk>/', views.admin_classroom_detail, name='admin-classroom-detail'),
    path('admin/academic/lecturer-assignments/', views.admin_lecturer_assignments, name='admin-lecturer-assignments'),
    path('admin/academic/lecturer-assignments/<str:assignment_type>/<int:pk>/', views.admin_delete_lecturer_assignment, name='admin-delete-lecturer-assignment'),
]
