
from rest_framework import generics
from rest_framework.parsers import FormParser, MultiPartParser
from accounts.permissions import IsAdmin
from .models import SemesterCalendar
from .serializers import SemesterCalendarSerializer


class SemesterCalendarListCreateView(generics.ListCreateAPIView):
    queryset = SemesterCalendar.objects.all()
    serializer_class = SemesterCalendarSerializer
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)