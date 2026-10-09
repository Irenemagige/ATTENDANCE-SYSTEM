
from django.urls import path
from .views import SemesterCalendarListCreateView

urlpatterns = [
    path(
        "",
        SemesterCalendarListCreateView.as_view(),
        name="semester-calendar-list-create",
    ),
]