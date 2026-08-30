from django.contrib import admin
from .models import AcademicYear, Semester, AcademicPeriod

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('year', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'name', 'start_date', 'end_date', 'is_active')
    list_filter = ('academic_year', 'is_active')

@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'semester', 'is_current')
    list_filter = ('is_current',)