from django.contrib import admin
from django.urls import include, path
from rest_framework import permissions

from accounts.views import api_root
from drf_yasg import openapi
from drf_yasg.views import get_schema_view

from django.conf import settings
from django.conf.urls.static import static

schema_view = get_schema_view(
    openapi.Info(
        title="Geofencing Attendance System API",
        default_version="v1",
        description="JWT authenticated attendance, course, and user management API.",
        contact=openapi.Contact(email="support@attendance.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path("api/", api_root, name="api_root"),
    path("api/", include("accounts.urls")),
    path("api/students/", include("students.urls"), name="students"),
    path("api/attendance/", include("attendance.urls"), name="attendance"),
    path("api/courses/", include("courses.urls"), name="courses"),
    path("api/departments/", include("departments.urls"), name="departments"),
    path("api-auth/", include("rest_framework.urls"), name="rest_framework"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="redoc"),
    path("api/subjects/", include("courses.subject_urls")),
    path(
    "api/academic-calendar/",
    include("academic_calendar.urls"),
),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )