from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
User = get_user_model()


# ========================
# DEPARTMENT MODELS
# ========================
class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ========================
# COURSE MODEL
# ========================
class Course(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ========================
# SUBJECT MODEL
# ========================
class Subject(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.course.name})"
    

class LecturerSubject(models.Model):
    lecturer = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('lecturer', 'subject')

    def __str__(self):
        return f"{self.lecturer.username} -> {self.subject.name}"


# ========================
# LECTURER ASSIGNMENT
# ========================
class LecturerAssignment(models.Model):
    lecturer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.lecturer.username} -> {self.subject.name}"
    

class LecturerCourse(models.Model):
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.lecturer.username} -> {self.course.name}"
    
class StudentCourse(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.student.username} -> {self.course.name}"
    
class Timetable(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="timetables",
    )

    subject = models.ForeignKey(
    Subject,
    on_delete=models.CASCADE,
    related_name="timetables",
)

    lecturer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    DAYS = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
        ("SUN", "Sunday"),
    ]

    day = models.CharField(max_length=10, choices=DAYS)

    start_time = models.TimeField()
    end_time = models.TimeField()

    room = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course} - {self.subject} - {self.day} {self.start_time}"
    
# ========================
# CLASSROOM MODEL
# ========================

class Classroom(models.Model):
    id = models.AutoField(primary_key=True)
    
    room_name = models.CharField(max_length=100)
    room_number = models.CharField(max_length=50)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    radius_meters = models.IntegerField(default=20)

    def __str__(self):
        return self.room_number
# ========================
# BLE BEACON MODEL
# ========================

class BLEBeacon(models.Model):

    beacon_name = models.CharField(
        max_length=100
    )


    beacon_id = models.CharField(
        max_length=100,
        unique=True
    )


    classroom = models.OneToOneField(
        Classroom,
        on_delete=models.CASCADE,
        related_name="beacon"
    )


    def __str__(self):
        return self.beacon_name

