from django.db import models

class AcademicYear(models.Model):
    year = models.CharField(max_length=9, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']
        indexes = [
            models.Index(fields=['year']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.year

class Semester(models.Model):
    SEMESTER_TYPES = (
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
    )
    name = models.CharField(max_length=20, choices=SEMESTER_TYPES)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='semesters')
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['academic_year', 'name']
        ordering = ['academic_year', 'name']

    def __str__(self):
        return f"{self.academic_year.year} - {self.get_name_display()}"

class AcademicPeriod(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='periods')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='periods')
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['academic_year', 'semester']
        ordering = ['-academic_year__year', '-semester__name']

    def __str__(self):
        return f"{self.academic_year} - {self.semester}"

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicPeriod.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)