from django.db import models
from django.contrib.auth import get_user_model
from students.models import Student
from lectures.models import Lecture
from academics.models import AcademicPeriod

User = get_user_model()

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE, related_name='attendances')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    check_in_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    distance_from_location = models.FloatField(null=True, blank=True, help_text="Distance in meters")
    device_identifier = models.CharField(max_length=200, blank=True)
    verification_code_used = models.CharField(max_length=20, blank=True)
    verification_result = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'lecture']
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['student', 'lecture']),
            models.Index(fields=['academic_period']),
            models.Index(fields=['check_in_time']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.lecture} - {self.get_status_display()}"

class AttendanceDevice(models.Model):
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE, related_name='device')
    device_fingerprint = models.CharField(max_length=200)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['device_fingerprint', 'attendance']),
        ]

    def __str__(self):
        return f"Device for {self.attendance}"