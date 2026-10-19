
from django.urls import path

from .views import (
    SemesterCalendarListCreateView,
    finalize_semester,
    student_semester_eligibility,
    admin_semester_eligibility,
    lecturer_semester_eligibility,
    hod_semester_eligibility,
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
    path(
        "<int:calendar_id>/eligibility/admin/",
        admin_semester_eligibility,
        name="admin-semester-eligibility",
    ),

    path(
    "<int:calendar_id>/eligibility/lecturer/",
    lecturer_semester_eligibility,
    name="lecturer-semester-eligibility",
    ),
    path(
    "<int:calendar_id>/eligibility/hod/",
    hod_semester_eligibility,
    name="hod-semester-eligibility",
),
]
