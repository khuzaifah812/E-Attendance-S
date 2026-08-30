from django.db import models
from django.contrib.auth import get_user_model
from academics.models import AcademicPeriod

User = get_user_model()

class Lecturer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lecturer_profile')
    staff_number = models.CharField(max_length=50, unique=True)
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['staff_number']
        indexes = [
            models.Index(fields=['staff_number']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.staff_number})"