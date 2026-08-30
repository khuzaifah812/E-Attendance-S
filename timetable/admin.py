from django.contrib import admin
from .models import Timetable

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('programme', 'course_unit', 'lecturer', 'day', 'start_time', 'end_time', 'room')
    list_filter = ('day', 'programme', 'academic_period')
    search_fields = ('programme__code', 'course_unit__code', 'course_unit__name')