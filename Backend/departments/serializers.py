from rest_framework import serializers
from courses.models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]
        read_only_fields = ["id"]
