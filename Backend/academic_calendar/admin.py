
from django.contrib import admin
from .models import SemesterCalendar, AcademicCalendarPeriod


class AcademicCalendarPeriodInline(admin.TabularInline):
    model = AcademicCalendarPeriod
    extra = 1


@admin.register(SemesterCalendar)
class SemesterCalendarAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "academic_year",
        "semester",
        "teaching_start_date",
        "teaching_end_date",
        "uploaded_by",
        "uploaded_at",
    )

    list_filter = ("academic_year", "semester")

    inlines = [AcademicCalendarPeriodInline]


@admin.register(AcademicCalendarPeriod)
class AcademicCalendarPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "calendar",
        "period_type",
        "start_date",
        "end_date",
    )

    list_filter = ("period_type", "calendar")