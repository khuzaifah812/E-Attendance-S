from django.contrib import admin
from .models import Programme

@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'session', 'is_active')
    list_filter = ('session', 'is_active')
    search_fields = ('code', 'name')