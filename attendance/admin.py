from django.contrib import admin
from .models import Attendance, AttendanceDevice

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'lecture', 'status', 'check_in_time')
    list_filter = ('status', 'academic_period')
    search_fields = ('student__registration_number', 'student__user__first_name', 'student__user__last_name')
    date_hierarchy = 'check_in_time'

@admin.register(AttendanceDevice)
class AttendanceDeviceAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'device_fingerprint', 'ip_address', 'created_at')
    search_fields = ('device_fingerprint', 'ip_address')