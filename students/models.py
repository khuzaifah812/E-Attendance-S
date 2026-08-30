from django.db import models
from django.contrib.auth import get_user_model
from programmes.models import Programme
from academics.models import AcademicPeriod

User = get_user_model()

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    registration_number = models.CharField(max_length=50, unique=True)
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name='students')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, null=True, blank=True)
    year_of_study = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration_number']
        indexes = [
            models.Index(fields=['registration_number']),
            models.Index(fields=['programme', 'academic_period']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.registration_number})"