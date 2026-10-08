from django.urls import path
from .views import assign_student_to_course, assign_lecturer_to_course
from . import views

urlpatterns = [
    path('assign-student/', assign_student_to_course, name='assign_student_to_course'),
    path('assign-lecturer/', assign_lecturer_to_course, name='assign_lecturer-to_course'),
    path('lecturer/', views.lecturer_courses, name='lecturer_courses'),
    path('subjects/', views.subject_list, name='subject_list'),
    path('classrooms/', views.classroom_list, name='classroom_list'),
    path('timetable/create/', views.create_timetable, name='create_timetable'),
    path(
    'timetable/upload/',
    views.upload_timetable_excel,
    name='upload_timetable_excel',
),
    path(
    'timetable/my/',
    views.my_timetable,
    name='my_timetable',
),
    path('', views.course_list, name='course_list'),
    path('create/', views.course_create, name='course_create'),
]