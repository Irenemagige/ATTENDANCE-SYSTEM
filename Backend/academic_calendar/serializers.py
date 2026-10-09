
from rest_framework import serializers
from .models import SemesterCalendar


class SemesterCalendarSerializer(serializers.ModelSerializer):
    document = serializers.FileField()

    class Meta:
        model = SemesterCalendar
        fields = [
            "id",
            "title",
            "academic_year",
            "semester",
            "document",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = ["id", "uploaded_by", "uploaded_at"]

    def validate_document(self, value):
        max_size = 10 * 1024 * 1024  # 10 MB

        if value.size > max_size:
            raise serializers.ValidationError(
                "The calendar document must not exceed 10 MB."
            )

        allowed_extensions = (".doc", ".docx", ".pdf")
        filename = value.name.lower()

        if not filename.endswith(allowed_extensions):
            raise serializers.ValidationError(
                "Upload a Word document (.doc or .docx) or PDF (.pdf)."
            )

        return value