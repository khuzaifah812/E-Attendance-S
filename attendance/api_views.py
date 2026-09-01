from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
import secrets
import math
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
        Student takes attendance for an active lecture with room coordinate validation
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
                    {'error': 'This lecture belongs to a different academic period.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify student is enrolled in this course
            if student.programme != lecture.programme:
                return Response(
                    {'error': 'You are not enrolled in this course.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check verification code
            if not lecture.verification_code:
                return Response(
                    {'error': 'No verification code has been generated. Please ask the lecturer to generate a code.'},
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
            
            # PHYSICAL LECTURE - Validate location against ROOM COORDINATES
            distance_from_room = None
            if lecture.lecture_type == 'PHYSICAL':
                # Check if room coordinates are set
                if not lecture.room_latitude or not lecture.room_longitude:
                    return Response(
                        {'error': 'Room coordinates not set for this lecture. Please contact the lecturer.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
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
                
                # Get room coordinates from lecture
                room_lat = float(lecture.room_latitude)
                room_lon = float(lecture.room_longitude)
                room_radius = lecture.room_radius or 50  # Default 50 meters
                
                # Check if student is within the room's allowed radius
                is_within_room, distance = self._check_location(latitude, longitude, room_lat, room_lon, room_radius)
                distance_from_room = distance
                
                if not is_within_room:
                    return Response({
                        'error': 'YOU ARE OUT OF THE CLASSROOM.',
                        'details': 'You are approximately ' + str(round(distance, 1)) + ' meters away from the classroom. Please move within ' + str(room_radius) + ' meters of the classroom.',
                        'distance': round(distance, 1),
                        'allowed_radius': room_radius,
                        'room_latitude': room_lat,
                        'room_longitude': room_lon,
                        'your_latitude': latitude,
                        'your_longitude': longitude
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # ONLINE LECTURE - Skip location validation
                latitude = None
                longitude = None
            
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
                device_identifier = 'device_' + secrets.token_hex(10)
            
            # Create attendance
            with transaction.atomic():
                attendance = Attendance.objects.create(
                    student=student,
                    lecture=lecture,
                    academic_period=current_period,
                    status='present',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    latitude=latitude,
                    longitude=longitude,
                    distance_from_location=distance_from_room,
                    device_identifier=device_identifier,
                    verification_code_used=verification_code,
                    verification_result='success',
                    notes='Lecture type: ' + lecture.lecture_type + ' | Room: ' + (lecture.location or 'Not specified')
                )
                
                # Create device record
                AttendanceDevice.objects.create(
                    attendance=attendance,
                    device_fingerprint=device_identifier,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    ip_address=request.META.get('REMOTE_ADDR', '')
                )
            
            # Get updated attendance statistics based on semester lectures
            stats = student.get_attendance_stats(current_period)
            
            # Get updated attendance count for this lecture
            attendance_count = lecture.attendances.count()
            
            response_data = {
                'success': True,
                'message': '✅ Attendance recorded successfully!',
                'attendance_id': attendance.id,
                'status': 'present',
                'lecture_type': lecture.lecture_type,
                'total_attendance': attendance_count,
                'student_stats': {
                    'total_lectures': stats['total_lectures'],
                    'attended': stats['attended'],
                    'present': stats['present'],
                    'late': stats['late'],
                    'absent': stats['absent'],
                    'percentage': stats['percentage']
                }
            }
            
            # Add location verification details for physical lectures
            if lecture.lecture_type == 'PHYSICAL':
                response_data['location_verified'] = True
                response_data['distance_from_room'] = round(distance_from_room, 1) if distance_from_room else None
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'An error occurred: ' + str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_location(self, student_lat, student_lon, room_lat, room_lon, radius=50):
        """
        Check if student is within the room's allowed radius using Haversine formula
        Returns: (is_within, distance_in_meters)
        """
        try:
            # Convert to radians
            lat1 = math.radians(float(student_lat))
            lon1 = math.radians(float(student_lon))
            lat2 = math.radians(float(room_lat))
            lon2 = math.radians(float(room_lon))
            
            # Haversine formula
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            distance = 6371000 * c  # Earth radius in meters
            
            return distance <= radius, distance
        except Exception as e:
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
                {'error': 'Failed to start lecture: ' + str(e)},
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
                {'error': 'Failed to end lecture: ' + str(e)},
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
                {'error': 'Failed to generate code: ' + str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_code(self, lecture):
        """
        Generate a secure verification code
        """
        code = 'UICT-' + secrets.token_hex(3).upper()
        lecture.verification_code = code
        lecture.code_expires_at = timezone.now() + timezone.timedelta(minutes=30)
        lecture.save()
        return code