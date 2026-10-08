from django.contrib import admin
from .models import Student, Notification


class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "reg_number",
        "full_name",
        "email",
    )


class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "title",
        "is_read",
        "created_at",
    )


admin.site.register(Student, StudentAdmin)
admin.site.register(Notification, NotificationAdmin)
