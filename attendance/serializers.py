from rest_framework import serializers
from .models import Attendance, AttendanceDevice

class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_reg = serializers.CharField(source='student.registration_number', read_only=True)
    lecture_title = serializers.CharField(source='lecture.title', read_only=True)
    lecture_type = serializers.CharField(source='lecture.lecture_type', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'student_reg', 'lecture', 'lecture_title',
            'lecture_type', 'academic_period', 'status', 'check_in_time', 'ip_address',
            'latitude', 'longitude', 'distance_from_location', 'device_identifier',
            'verification_code_used', 'verification_result', 'notes', 'created_at'
        ]
        read_only_fields = ['check_in_time', 'created_at']

class AttendanceDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceDevice
        fields = '__all__'