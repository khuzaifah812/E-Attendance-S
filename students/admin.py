from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'user', 'programme', 'year_of_study', 'is_active')
    list_filter = ('programme', 'is_active', 'academic_period')
    search_fields = ('registration_number', 'user__username', 'user__first_name', 'user__last_name')