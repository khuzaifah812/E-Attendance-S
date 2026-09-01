from django.db import models
from django.contrib.auth import get_user_model
from programmes.models import Programme
from academics.models import AcademicPeriod
from lectures.models import Lecture
from attendance.models import Attendance

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
    
    def get_total_lectures_for_period(self, academic_period=None):
        """
        Get total number of lectures available for this student in a given period
        Counts all scheduled, active, and completed lectures (excludes cancelled)
        """
        if academic_period is None:
            academic_period = self.academic_period
        
        if not academic_period:
            return 0
        
        # Get all lectures for the student's programme in this period
        # Only count lectures that are scheduled (not cancelled)
        total_lectures = Lecture.objects.filter(
            programme=self.programme,
            academic_period=academic_period,
            status__in=['scheduled', 'active', 'completed']
        ).count()
        
        return total_lectures
    
    def get_attendance_stats(self, academic_period=None):
        """
        Get attendance statistics for this student
        Returns: dict with total_lectures, present, absent, late, excused, attended, percentage
        """
        if academic_period is None:
            academic_period = self.academic_period
        
        if not academic_period:
            return {
                'total_lectures': 0,
                'present': 0,
                'absent': 0,
                'late': 0,
                'excused': 0,
                'attended': 0,
                'percentage': 0
            }
        
        # Get total lectures available in the semester
        total_lectures = self.get_total_lectures_for_period(academic_period)
        
        # Get student's attendance records
        attendances = Attendance.objects.filter(
            student=self,
            academic_period=academic_period
        )
        
        present = attendances.filter(status='present').count()
        late = attendances.filter(status='late').count()
        excused = attendances.filter(status='excused').count()
        attended = present + late  # Present + Late count as attended
        
        # Calculate absent (total lectures - attended)
        absent = total_lectures - attended
        
        # Calculate percentage based on total lectures
        if total_lectures > 0:
            percentage = (attended / total_lectures) * 100
        else:
            percentage = 0
        
        return {
            'total_lectures': total_lectures,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attended': attended,
            'percentage': percentage
        }