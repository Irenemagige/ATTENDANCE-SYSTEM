from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    path("api/attendance/", include("attendance.urls")),
    path("api/", include("accounts.urls")),
    path("api/students/", include("students.urls")),
    path("api/device/", include("accounts.device_urls")),
    
]