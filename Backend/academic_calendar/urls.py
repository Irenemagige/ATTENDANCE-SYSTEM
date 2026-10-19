from django.urls import path

from .views import (
    SemesterCalendarListCreateView,
    finalize_semester,
    student_semester_eligibility,
)

urlpatterns = [
    path(
        "",
        SemesterCalendarListCreateView.as_view(),
        name="semester-calendar-list-create",
    ),
    path(
        "<int:calendar_id>/finalize/",
        finalize_semester,
        name="finalize-semester",
    ),
    path(
        "<int:calendar_id>/eligibility/",
        student_semester_eligibility,
        name="student-semester-eligibility",
    ),
]