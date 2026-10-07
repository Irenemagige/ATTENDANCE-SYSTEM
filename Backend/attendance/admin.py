from django.contrib import admin
from django.contrib.auth import get_user_model

from attendance.models import Attendance, AttendanceSession, MovementLog

User = get_user_model()


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "course",
        "subject",
        "lecturer",
        "start_time",
        "end_time",
        "ended_at",
        "checkout_deadline",
        "auto_closed",
        "date",
        "is_active",
        "radius_meters",
        "created_at",
    )
    search_fields = ("course__name", "course__code", "subject__name", "lecturer__username")
    list_filter = ("is_active", "date", "course")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "lecturer":
            kwargs["queryset"] = User.objects.filter(groups__name__iexact="Lecturer")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "session", "status", "check_in_time", "check_out_time")
    search_fields = ("student__reg_number", "student__full_name", "session__subject__name")
    list_filter = ("status", "session__course", "session__date")
admin.site.register(MovementLog)