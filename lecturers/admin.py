from django.contrib import admin
from .models import Lecturer

@admin.register(Lecturer)
class LecturerAdmin(admin.ModelAdmin):
    list_display = ('staff_number', 'user', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('staff_number', 'user__username', 'user__first_name', 'user__last_name')