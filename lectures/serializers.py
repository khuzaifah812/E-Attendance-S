from rest_framework import serializers
from .models import Lecture

class LectureSerializer(serializers.ModelSerializer):
    course_unit_name = serializers.CharField(source='course_unit.name', read_only=True)
    course_unit_code = serializers.CharField(source='course_unit.code', read_only=True)
    lecturer_name = serializers.CharField(source='lecturer.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lecture_type_display = serializers.CharField(source='get_lecture_type_display', read_only=True)
    
    class Meta:
        model = Lecture
        fields = [
            'id', 'course_unit', 'course_unit_name', 'course_unit_code',
            'lecturer', 'lecturer_name', 'academic_period', 'programme',
            'title', 'lecture_type', 'lecture_type_display', 'status',
            'status_display', 'scheduled_date', 'start_time', 'end_time',
            'actual_start', 'actual_end', 'location', 'verification_code',
            'code_expires_at', 'max_attempts', 'created_at', 'updated_at'
        ]
        read_only_fields = ['actual_start', 'actual_end', 'verification_code', 'code_expires_at']