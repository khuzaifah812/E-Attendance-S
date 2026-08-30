from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
import secrets
import math
import json
from .models import Attendance, AttendanceDevice
from lectures.models import Lecture
from students.models import Student
from academics.models import AcademicPeriod
from .serializers import AttendanceSerializer
from .permissions import IsStudent, IsLecturer, IsAdmin

User = get_user_model()

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action == 'take_attendance':
            self.permission_classes = [IsAuthenticated, IsStudent]
        elif self.action in ['start_lecture', 'end_lecture', 'generate_code']:
            self.permission_classes = [IsAuthenticated, IsLecturer]
        return super().get_permissions()
    
    @action(detail=False, methods=['post'])
    def take_attendance(self, request):
        """
        Student takes attendance for an active lecture
        """
        try:
            # Get student profile
            try:
                student = request.user.student_profile
            except Student.DoesNotExist:
                return Response(
                    {'error': 'Student profile not found. Please contact the administrator.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get request data
            lecture_id = request.data.get('lecture_id')
            verification_code = request.data.get('verification_code', '').strip().upper()
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            device_identifier = request.data.get('device_identifier', '')
            
            # Validate required fields
            if not lecture_id:
                return Response(
                    {'error': 'Lecture ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not verification_code:
                return Response(
                    {'error': 'Verification code is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get lecture
            try:
                lecture = Lecture.objects.get(id=lecture_id)
            except Lecture.DoesNotExist:
                return Response(
                    {'error': 'Lecture not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if lecture is active
            if lecture.status != 'active':
                return Response(
                    {'error': 'Lecture is not active. Please wait for the lecturer to start the lecture.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check time window
            now = timezone.now()
            if lecture.actual_start and now < lecture.actual_start:
                return Response(
                    {'error': 'Attendance has not started yet.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if lecture.actual_end and now > lecture.actual_end:
                return Response(
                    {'error': 'Attendance has ended. The lecturer has closed the attendance.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check academic period
            current_period = AcademicPeriod.objects.filter(is_current=True).first()
            if not current_period:
                return Response(
                    {'error': 'No active academic period found. Please contact the administrator.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if lecture.academic_period != current_period:
                return Response(
                    {'error': f'This lecture belongs to a different academic period. Current period: {current_period}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify student is enrolled in this course
            if student.programme != lecture.programme:
                return Response(
                    {'error': f'You are not enrolled in this course. This lecture is for {lecture.programme.name} students.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check verification code
            if not lecture.verification_code:
                return Response(
                    {'error': 'No verification code has been generated for this lecture. Please ask the lecturer to generate a code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if lecture.verification_code != verification_code:
                return Response(
                    {'error': 'Invalid verification code. Please check the code and try again.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if lecture.code_expires_at and now > lecture.code_expires_at:
                return Response(
                    {'error': 'Verification code has expired. Please ask the lecturer to generate a new code.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check duplicate attendance
            if Attendance.objects.filter(student=student, lecture=lecture).exists():
                return Response(
                    {'error': 'You have already taken attendance for this lecture.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Physical lecture location validation
            if lecture.lecture_type == 'PHYSICAL':
                if not latitude or not longitude:
                    return Response(
                        {'error': 'LOCATION PERMISSION IS REQUIRED. Please allow location access to take attendance for physical lectures.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    latitude = float(latitude)
                    longitude = float(longitude)
                except (ValueError, TypeError):
                    return Response(
                        {'error': 'Invalid location coordinates.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if student is within campus
                is_within_campus, distance = self._check_location(latitude, longitude)
                if not is_within_campus:
                    return Response(
                        {'error': f'YOU ARE OUT OF THE CLASSROOM. You are approximately {distance:.0f} meters away from the campus. Please move within 100 meters of the campus to take attendance.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Online lecture - skip location validation
            # No location check for online lectures
            
            # Check device restriction
            if device_identifier:
                used_device = AttendanceDevice.objects.filter(
                    device_fingerprint=device_identifier,
                    attendance__lecture=lecture
                ).exclude(attendance__student=student).exists()
                
                if used_device:
                    return Response(
                        {'error': 'THIS DEVICE HAS ALREADY BEEN USED FOR ATTENDANCE. YOU CANNOT TAKE ATTENDANCE FOR ANOTHER STUDENT.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Generate device identifier if not provided
                device_identifier = f"unknown_{secrets.token_hex(8)}"
                # Try to get from request headers
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                if user_agent:
                    device_identifier = f"device_{hash(user_agent)}_{secrets.token_hex(4)}"
                    localStorage_id = request.data.get('device_identifier', '')
                    if localStorage_id:
                        device_identifier = localStorage_id
                else:
                    device_identifier = f"device_{secrets.token_hex(10)}"
            
            # Create attendance
            with transaction.atomic():
                attendance = Attendance.objects.create(
                    student=student,
                    lecture=lecture,
                    academic_period=current_period,
                    status='present',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    latitude=latitude if lecture.lecture_type == 'PHYSICAL' else None,
                    longitude=longitude if lecture.lecture_type == 'PHYSICAL' else None,
                    device_identifier=device_identifier,
                    verification_code_used=verification_code,
                    verification_result='success',
                    notes=f"Lecture type: {lecture.lecture_type}"
                )
                
                # Create device record
                AttendanceDevice.objects.create(
                    attendance=attendance,
                    device_fingerprint=device_identifier,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    ip_address=request.META.get('REMOTE_ADDR', '')
                )
            
            # Get updated attendance count
            attendance_count = lecture.attendances.count()
            
            return Response({
                'success': True,
                'message': '✅ Attendance recorded successfully!',
                'attendance_id': attendance.id,
                'status': 'present',
                'lecture_type': lecture.lecture_type,
                'total_attendance': attendance_count
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_location(self, latitude, longitude):
        """
        Check if student is within campus (simplified)
        In production, use actual campus coordinates from settings
        """
        # Campus coordinates - UPDATE THESE WITH YOUR ACTUAL CAMPUS COORDINATES
        campus_lat = 0.0  # Replace with your campus latitude
        campus_lon = 0.0  # Replace with your campus longitude
        radius = 100  # meters (allowed radius)
        
        try:
            lat1 = math.radians(float(latitude))
            lon1 = math.radians(float(longitude))
            lat2 = math.radians(campus_lat)
            lon2 = math.radians(campus_lon)
            
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            distance = 6371000 * c  # Earth radius in meters
            
            return distance <= radius, distance
        except:
            return False, 999999
    
    @action(detail=False, methods=['post'])
    def start_lecture(self, request):
        """
        Lecturer starts a lecture
        """
        try:
            lecture_id = request.data.get('lecture_id')
            
            if not lecture_id:
                return Response(
                    {'error': 'Lecture ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            lecture = get_object_or_404(Lecture, id=lecture_id, lecturer=request.user)
            
            if lecture.status == 'active':
                return Response(
                    {'error': 'Lecture is already active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if lecture.status == 'completed':
                return Response(
                    {'error': 'Lecture has already been completed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Start lecture
            lecture.status = 'active'
            lecture.actual_start = timezone.now()
            lecture.save()
            
            # Generate verification code
            code = self._generate_code(lecture)
            
            return Response({
                'success': True,
                'message': '✅ Lecture started successfully!',
                'verification_code': code,
                'lecture_id': lecture.id,
                'lecture_type': lecture.lecture_type,
                'start_time': lecture.actual_start.isoformat()
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to start lecture: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def end_lecture(self, request):
        """
        Lecturer ends a lecture
        """
        try:
            lecture_id = request.data.get('lecture_id')
            
            if not lecture_id:
                return Response(
                    {'error': 'Lecture ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            lecture = get_object_or_404(Lecture, id=lecture_id, lecturer=request.user)
            
            if lecture.status != 'active':
                return Response(
                    {'error': 'Lecture is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # End lecture
            lecture.status = 'completed'
            lecture.actual_end = timezone.now()
            lecture.verification_code = ''
            lecture.code_expires_at = None
            lecture.save()
            
            total_attendance = lecture.attendances.count()
            
            return Response({
                'success': True,
                'message': '✅ Lecture ended successfully!',
                'lecture_id': lecture.id,
                'end_time': lecture.actual_end.isoformat(),
                'total_attendance': total_attendance
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to end lecture: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def generate_code(self, request):
        """
        Generate or refresh verification code
        """
        try:
            lecture_id = request.data.get('lecture_id')
            
            if not lecture_id:
                return Response(
                    {'error': 'Lecture ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            lecture = get_object_or_404(Lecture, id=lecture_id, lecturer=request.user)
            
            if lecture.status != 'active':
                return Response(
                    {'error': 'Lecture must be active to generate a code'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate new code
            code = self._generate_code(lecture)
            
            return Response({
                'success': True,
                'message': '✅ New verification code generated!',
                'verification_code': code,
                'expires_at': lecture.code_expires_at.isoformat() if lecture.code_expires_at else None
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to generate code: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_code(self, lecture):
        """
        Generate a secure verification code
        """
        code = f"UICT-{secrets.token_hex(3).upper()}"
        lecture.verification_code = code
        lecture.code_expires_at = timezone.now() + timezone.timedelta(minutes=30)
        lecture.save()
        return code