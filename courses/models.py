from django.db import models
from django.contrib.auth import get_user_model
from programmes.models import Programme
from academics.models import AcademicPeriod

User = get_user_model()

class CourseUnit(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name='course_units')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT)
    lecturer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='course_units', limit_choices_to={'role': 'lecturer'})
    year_of_study = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['programme', 'academic_period']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"