from rest_framework import serializers
from .models import SemesterCalendar, AcademicCalendarPeriod


class SemesterCalendarSerializer(serializers.ModelSerializer):
    document = serializers.FileField()

    class Meta:
        model = SemesterCalendar
        fields = [
            "id", "title", "academic_year", "semester", "document",
            "teaching_start_date", "teaching_end_date",
            "is_finalized", "finalized_at", "finalized_by",
            "uploaded_by", "uploaded_at",
        ]
        read_only_fields = [
            "id", "is_finalized", "finalized_at", "finalized_by",
            "uploaded_by", "uploaded_at",
        ]
        
    extra_kwargs = {
    "title": {"required": False, "allow_blank": True},
    "academic_year": {"required": False, "allow_blank": True},
    "semester": {"required": False, "allow_blank": True},
    "teaching_start_date": {"required": False, "allow_null": True},
    "teaching_end_date": {"required": False, "allow_null": True},
}

    def validate_document(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "The calendar document must not exceed 10 MB."
            )

        if not value.name.lower().endswith((".doc", ".docx", ".pdf")):
            raise serializers.ValidationError(
                "Upload a Word document (.doc or .docx) or PDF (.pdf)."
            )

        return value

    def validate(self, attrs):
        start = attrs.get(
            "teaching_start_date",
            getattr(self.instance, "teaching_start_date", None),
        )
        end = attrs.get(
            "teaching_end_date",
            getattr(self.instance, "teaching_end_date", None),
        )
        if start and end and end < start:
            raise serializers.ValidationError({
                "teaching_end_date": "The teaching end date cannot precede the start date."
            })
        return attrs


class AcademicCalendarPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicCalendarPeriod
        fields = [
            "id", "calendar", "name", "period_type",
            "start_date", "end_date", "notes",
        ]
        read_only_fields = ["id", "calendar"]

    def validate(self, attrs):
        start = attrs.get(
            "start_date",
            getattr(self.instance, "start_date", None),
        )
        end = attrs.get(
            "end_date",
            getattr(self.instance, "end_date", None),
        )
        if start and end and end < start:
            raise serializers.ValidationError({
                "end_date": "The end date cannot precede the start date."
            })
        return attrs
