from django.contrib import admin
from .models import Lecture

@admin.register(Lecture)
class LectureAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_unit', 'lecturer', 'lecture_type', 'status', 'scheduled_date')
    list_filter = ('lecture_type', 'status', 'academic_period')
    search_fields = ('title', 'course_unit__code', 'course_unit__name')
    date_hierarchy = 'scheduled_date'