from django.db import models

class Programme(models.Model):
    SESSION_CHOICES = (
        ('DAY', 'Day'),
        ('WEEKEND', 'Weekend'),
        ('EVENING', 'Evening'),
    )
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    duration = models.IntegerField(help_text="Duration in semesters")
    session = models.CharField(max_length=10, choices=SESSION_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"