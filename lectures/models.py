from django.db import models
from django.contrib.auth import get_user_model
from courses.models import CourseUnit
from academics.models import AcademicPeriod
from programmes.models import Programme

User = get_user_model()

class Lecture(models.Model):
    LECTURE_TYPES = (
        ('PHYSICAL', 'Physical'),
        ('ONLINE', 'Online'),
    )
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    course_unit = models.ForeignKey(CourseUnit, on_delete=models.CASCADE, related_name='lectures')
    lecturer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='lectures', limit_choices_to={'role': 'lecturer'})
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT)
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    lecture_type = models.CharField(max_length=10, choices=LECTURE_TYPES, default='PHYSICAL')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    verification_code = models.CharField(max_length=20, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    max_attempts = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-start_time']
        indexes = [
            models.Index(fields=['course_unit', 'academic_period']),
            models.Index(fields=['lecturer', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['verification_code']),
        ]

    def __str__(self):
        return f"{self.course_unit} - {self.scheduled_date} ({self.get_lecture_type_display()})"