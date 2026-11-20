from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Student, Notification
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsStudent



from attendance.models import Attendance, AttendanceSession

@api_view(["GET"])
@permission_classes([IsStudent])
def student_dashboard(request):
    user = request.user

    try:
        # ✅ correct direction: User → Student
        student = Student.objects.get(user=user)
        total_sessions = Attendance.objects.filter(
        student=student
        ).count()

        attendance_records = Attendance.objects.filter(
        student=student
        )

# Calculate overall attendance using the actual
# attendance percentage recorded for each session.
        total_percentage = sum(
        float(record.attendance_percentage or 0)
        for record in attendance_records
        )

        percentage = (
        total_percentage / total_sessions
        if total_sessions > 0
        else 0
       )

        percentage = round(percentage, 2)

        attended_sessions = attendance_records.filter(
        status__in=[
            "PRESENT",
            "LATE",
            "PARTIAL_ATTENDANCE"
            ]
            ).count()

        total_absent = attendance_records.filter(
            status="ABSENT"
            ).count()
        status = "Fine" if percentage >= 50 else "Critical"

        return Response({
            "success": True,
            "data": {
                "name": student.full_name,
                "course": student.course.name,
                "department": getattr(getattr(student.course, "department", None), "name", None),
                "year": student.year_of_study,
                "present": attended_sessions,
                "absent": total_absent,
                "total_sessions": total_sessions,
                "attended_sessions": attended_sessions,
                "percentage": percentage,
                "status": status
            }
        })

    except Student.DoesNotExist:
        return Response({
            "success": False,
            "message": "Student profile not found"
        }, status=404)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notifications(request):

    try:
        student = Student.objects.get(user=request.user)

        # Get only latest 20 notifications
        notifications = Notification.objects.filter(
            student=student
        ).order_by("-created_at")[:20]


        # Count unread notifications
        unread_count = Notification.objects.filter(
            student=student,
            is_read=False
        ).count()


        data = [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "read": n.is_read,
                "created": n.created_at
            }
            for n in notifications
        ]


        return Response({
            "unread_count": unread_count,
            "total_returned": len(data),
            "notifications": data
        })


    except Student.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Student profile not found"
            },
            status=404
        )
        
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):

    try:
        student = Student.objects.get(
            user=request.user
        )

        notification = Notification.objects.get(
            id=notification_id,
            student=student
        )

        notification.is_read = True
        notification.save()

        return Response({
            "success": True,
            "message": "Notification marked as read"
        })


    except Notification.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Notification not found"
            },
            status=404
        )
        
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):

    try:
        student = Student.objects.get(
            user=request.user
        )

        updated = Notification.objects.filter(
            student=student,
            is_read=False
        ).update(
            is_read=True
        )

        return Response({
            "success": True,
            "message": "All notifications marked as read",
            "updated_count": updated
        })


    except Student.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Student profile not found"
            },
            status=404
        )