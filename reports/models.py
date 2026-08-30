from django.db import models
from django.contrib.auth import get_user_model
from academics.models import AcademicPeriod

User = get_user_model()

class Report(models.Model):
    REPORT_TYPES = (
        ('attendance', 'Attendance Report'),
        ('student', 'Student Report'),
        ('lecturer', 'Lecturer Report'),
        ('course', 'Course Report'),
    )
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    title = models.CharField(max_length=200)
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT)
    filters = models.JSONField(default=dict)
    file_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.title}"