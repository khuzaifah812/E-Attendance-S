from django.contrib import admin
from .models import CourseUnit

@admin.register(CourseUnit)
class CourseUnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'programme', 'lecturer', 'year_of_study', 'is_active')
    list_filter = ('programme', 'is_active', 'academic_period')
    search_fields = ('code', 'name')