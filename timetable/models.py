from django.db import models
from academics.models import AcademicPeriod
from courses.models import CourseUnit
from programmes.models import Programme
from django.contrib.auth import get_user_model

User = get_user_model()

class Timetable(models.Model):
    DAY_CHOICES = (
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    )
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='timetables')
    course_unit = models.ForeignKey(CourseUnit, on_delete=models.CASCADE, related_name='timetables')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT)
    lecturer = models.ForeignKey(User, on_delete=models.PROTECT, limit_choices_to={'role': 'lecturer'})
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['programme', 'day', 'start_time', 'room']
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.programme} - {self.course_unit} - {self.get_day_display()} {self.start_time}"