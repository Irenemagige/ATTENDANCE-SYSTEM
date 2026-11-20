from rest_framework import generics
from accounts.permissions import IsAdminOrStaff
from courses.models import Department
from .serializers import DepartmentSerializer


class DepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrStaff]


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrStaff]
