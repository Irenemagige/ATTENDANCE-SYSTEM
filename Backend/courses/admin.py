from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Classroom, BLEBeacon




from courses.models import (
    Course,
    Department,
    LecturerAssignment,
    LecturerCourse,
    LecturerSubject,
    StudentCourse,
    Subject,
    Timetable,
)

User = get_user_model()


class GroupFilteredUserAdminMixin:
    user_group_filters = {}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        group_name = self.user_group_filters.get(db_field.name)
        if group_name:
            kwargs["queryset"] = User.objects.filter(groups__name__iexact=group_name)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "created_at")
    search_fields = ("code", "name", "department__name")
    list_filter = ("department",)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "course")
    search_fields = ("code", "name", "course__name")
    list_filter = ("course",)


@admin.register(LecturerSubject)
class LecturerSubjectAdmin(GroupFilteredUserAdminMixin, admin.ModelAdmin):
    user_group_filters = {"lecturer": "Lecturer"}
    list_display = ("lecturer", "subject")
    search_fields = ("lecturer__username", "subject__name", "subject__code")
    list_filter = ("subject__course",)


@admin.register(LecturerAssignment)
class LecturerAssignmentAdmin(GroupFilteredUserAdminMixin, admin.ModelAdmin):
    user_group_filters = {"lecturer": "Lecturer"}
    list_display = ("lecturer", "subject")
    search_fields = ("lecturer__username", "subject__name", "subject__code")
    list_filter = ("subject__course",)


@admin.register(LecturerCourse)
class LecturerCourseAdmin(GroupFilteredUserAdminMixin, admin.ModelAdmin):
    user_group_filters = {"lecturer": "Lecturer"}
    list_display = ("lecturer", "course")
    search_fields = ("lecturer__username", "course__name", "course__code")
    list_filter = ("course",)


@admin.register(StudentCourse)
class StudentCourseAdmin(GroupFilteredUserAdminMixin, admin.ModelAdmin):
    user_group_filters = {"student": "Student"}
    list_display = ("student", "course")
    search_fields = ("student__username", "course__name", "course__code")
    list_filter = ("course",)


@admin.register(Timetable)
class TimetableAdmin(GroupFilteredUserAdminMixin, admin.ModelAdmin):
    user_group_filters = {"lecturer": "Lecturer"}

    list_display = (
        "course",
        "subject",
        "lecturer",
        "day",
        "start_time",
        "end_time",
        "room",
    )

    search_fields = (
        "course__name",
        "course__code",
        "subject__name",
        "subject__code",
        "lecturer__username",
        "room",
    )

    list_filter = (
        "day",
        "course",
        "subject",
        "lecturer",
    )
    
@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "room_name",
        "room_number",
        "latitude",
        "longitude",
        "radius_meters",
    )
admin.site.register(BLEBeacon)
