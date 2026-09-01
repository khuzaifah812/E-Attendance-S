from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from students.models import Student
from academics.models import AcademicPeriod, AcademicYear, Semester
from attendance.models import Attendance
from lectures.models import Lecture
from courses.models import CourseUnit
from programmes.models import Programme
from coordinators.models import Coordinator
from lecturers.models import Lecturer
from django.contrib.auth import get_user_model
import json
import re
import secrets
import string
from datetime import datetime

User = get_user_model()


# ==================== AUTHENTICATION VIEWS ====================

def login_view(request):
    """
    Custom login view for UICT-ESAS
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            return render(request, 'core/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Update last login IP
            user.last_login_ip = request.META.get('REMOTE_ADDR')
            user.save()
            
            # Check if first login (student with default password)
            if not user.is_verified and user.role == 'student':
                messages.info(request, 'Please change your default password to continue.')
                return redirect('change_password')
            
            # Redirect to dashboard based on role
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    
    return render(request, 'core/login.html')


@login_required
def logout_view(request):
    """
    Custom logout view
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard(request):
    """
    Main dashboard router - redirects to role-specific dashboard
    """
    user = request.user
    
    context = {
        'user': user,
        'academic_period': AcademicPeriod.objects.filter(is_current=True).first(),
    }
    
    if user.role == 'student':
        return student_dashboard(request)
    elif user.role == 'lecturer':
        return lecturer_dashboard(request)
    elif user.role == 'coordinator':
        return coordinator_dashboard(request)
    elif user.role == 'admin':
        return admin_dashboard(request)
    else:
        messages.error(request, 'Unknown user role. Please contact the administrator.')
        return redirect('login')


# ==================== DASHBOARD VIEWS ====================

@login_required
def student_dashboard(request):
    """
    Student Dashboard - View attendance, lectures, and take attendance
    """
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found. Please contact the administrator.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    
    if current_period:
        stats = student.get_attendance_stats(current_period)
    else:
        stats = {
            'total_lectures': 0,
            'present': 0,
            'absent': 0,
            'late': 0,
            'excused': 0,
            'attended': 0,
            'percentage': 0
        }
    
    today = timezone.now().date()
    if current_period:
        today_lectures = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date=today
        ).order_by('start_time')
        
        for lecture in today_lectures:
            lecture.has_attended = Attendance.objects.filter(
                student=student,
                lecture=lecture
            ).exists()
    else:
        today_lectures = []
    
    active_lecture = None
    if current_period:
        active_lecture = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date=today,
            status='active'
        ).first()
    
    next_week = today + timezone.timedelta(days=7)
    if current_period:
        upcoming_lectures = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date__gt=today,
            scheduled_date__lte=next_week,
            status__in=['scheduled', 'active']
        ).order_by('scheduled_date', 'start_time')[:5]
    else:
        upcoming_lectures = []
    
    if current_period:
        attendance_history = Attendance.objects.filter(
            student=student,
            academic_period=current_period
        ).select_related('lecture', 'lecture__course_unit').order_by('-check_in_time')[:10]
    else:
        attendance_history = []
    
    context = {
        'student': student,
        'academic_period': current_period,
        'total_lectures': stats['total_lectures'],
        'present': stats['present'],
        'absent': stats['absent'],
        'late': stats['late'],
        'excused': stats['excused'],
        'attended': stats['attended'],
        'attendance_percentage': stats['percentage'],
        'today_lectures': today_lectures,
        'active_lecture': active_lecture,
        'has_active_lecture': active_lecture is not None,
        'upcoming_lectures': upcoming_lectures,
        'attendance_history': attendance_history,
        'page_title': 'Student Dashboard'
    }
    return render(request, 'student/dashboard.html', context)


@login_required
def lecturer_dashboard(request):
    """
    Lecturer Dashboard - View courses, lectures, and manage attendance
    """
    try:
        lecturer_profile = request.user.lecturer_profile
    except Lecturer.DoesNotExist:
        messages.error(request, 'Lecturer profile not found. Please contact the administrator.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    today = timezone.now().date()
    
    if current_period:
        today_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date=today
        ).order_by('start_time')
        
        assigned_courses = CourseUnit.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            is_active=True
        )
        
        active_lecture = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date=today,
            status='active'
        ).first()
        
        next_week = today + timezone.timedelta(days=7)
        upcoming_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date__gt=today,
            scheduled_date__lte=next_week,
            status='scheduled'
        ).order_by('scheduled_date', 'start_time')[:10]
        
        recent_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date__lt=today
        ).order_by('-scheduled_date', '-start_time')[:5]
        
        attendance_stats = {}
        if active_lecture:
            total_students = Student.objects.filter(
                programme=active_lecture.programme,
                is_active=True
            ).count()
            present_students = active_lecture.attendances.filter(status='present').count()
            attendance_stats = {
                'total': total_students,
                'present': present_students,
                'absent': total_students - present_students,
                'percentage': (present_students / total_students * 100) if total_students > 0 else 0
            }
    else:
        today_lectures = []
        assigned_courses = []
        active_lecture = None
        upcoming_lectures = []
        recent_lectures = []
        attendance_stats = {}
    
    context = {
        'lecturer_profile': lecturer_profile,
        'academic_period': current_period,
        'today_lectures': today_lectures,
        'assigned_courses': assigned_courses,
        'active_lecture': active_lecture,
        'has_active_lecture': active_lecture is not None,
        'upcoming_lectures': upcoming_lectures,
        'recent_lectures': recent_lectures,
        'attendance_stats': attendance_stats,
        'page_title': 'Lecturer Dashboard'
    }
    return render(request, 'lecturer/dashboard.html', context)


@login_required
def coordinator_dashboard(request):
    """
    Coordinator Dashboard - Monitor students, lecturers, and attendance
    """
    try:
        coordinator_profile = request.user.coordinator_profile
    except Coordinator.DoesNotExist:
        messages.error(request, 'Coordinator profile not found. Please contact the administrator.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    today = timezone.now().date()
    
    total_students = Student.objects.filter(is_active=True).count()
    total_lecturers = User.objects.filter(role='lecturer', is_active=True).count()
    total_programmes = Programme.objects.filter(is_active=True).count()
    total_course_units = CourseUnit.objects.filter(is_active=True).count()
    
    today_lectures = Lecture.objects.filter(
        scheduled_date=today
    ).count() if current_period else 0
    
    active_lectures = Lecture.objects.filter(
        status='active'
    ).count() if current_period else 0
    
    if current_period:
        students = Student.objects.filter(is_active=True)
        
        total_attended = 0
        total_possible = 0
        total_lectures_semester = 0
        
        for student in students:
            stats = student.get_attendance_stats(current_period)
            total_attended += stats['attended']
            total_possible += stats['total_lectures']
            if stats['total_lectures'] > 0 and total_lectures_semester == 0:
                total_lectures_semester = stats['total_lectures']
        
        if total_possible > 0 and students.count() > 0:
            overall_percentage = (total_attended / total_possible) * 100
        else:
            overall_percentage = 0
        
        recent_attendances = Attendance.objects.filter(
            academic_period=current_period
        ).select_related('student', 'student__user', 'lecture', 'lecture__course_unit').order_by('-check_in_time')[:20]
    else:
        total_attended = 0
        total_possible = 0
        total_lectures_semester = 0
        overall_percentage = 0
        recent_attendances = []
    
    context = {
        'coordinator_profile': coordinator_profile,
        'academic_period': current_period,
        'total_students': total_students,
        'total_lecturers': total_lecturers,
        'total_programmes': total_programmes,
        'total_course_units': total_course_units,
        'today_lectures': today_lectures,
        'active_lectures': active_lectures,
        'total_attended': total_attended,
        'total_possible': total_possible,
        'total_lectures_semester': total_lectures_semester,
        'overall_percentage': overall_percentage,
        'recent_attendances': recent_attendances,
        'page_title': 'Coordinator Dashboard'
    }
    return render(request, 'coordinator/dashboard.html', context)


@login_required
def admin_dashboard(request):
    """
    Administrator Dashboard - Full system management
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    today = timezone.now().date()
    
    total_students = Student.objects.filter(is_active=True).count()
    total_lecturers = User.objects.filter(role='lecturer', is_active=True).count()
    total_coordinators = User.objects.filter(role='coordinator', is_active=True).count()
    total_programmes = Programme.objects.filter(is_active=True).count()
    total_course_units = CourseUnit.objects.filter(is_active=True).count()
    
    today_lectures = Lecture.objects.filter(scheduled_date=today).count()
    active_lectures = Lecture.objects.filter(status='active').count()
    
    if current_period:
        total_lectures_semester = Lecture.objects.filter(
            academic_period=current_period,
            status__in=['scheduled', 'active', 'completed']
        ).count()
    else:
        total_lectures_semester = 0
    
    if current_period:
        students = Student.objects.filter(is_active=True)
        total_attended = 0
        total_possible = 0
        
        for student in students:
            stats = student.get_attendance_stats(current_period)
            total_attended += stats['attended']
            total_possible += stats['total_lectures']
        
        if total_possible > 0:
            overall_attendance = (total_attended / total_possible) * 100
        else:
            overall_attendance = 0
        
        total_attendances = Attendance.objects.filter(
            academic_period=current_period
        ).count()
    else:
        total_attended = 0
        total_possible = 0
        overall_attendance = 0
        total_attendances = 0
    
    today_attendances = Attendance.objects.filter(
        check_in_time__date=today
    ) if current_period else Attendance.objects.none()
    today_present = today_attendances.filter(status='present').count()
    
    recent_attendances = Attendance.objects.filter(
        academic_period=current_period
    ).select_related('student', 'student__user', 'lecture').order_by('-check_in_time')[:15] if current_period else []
    
    recent_lectures = Lecture.objects.filter(
        academic_period=current_period
    ).order_by('-scheduled_date', '-start_time')[:10] if current_period else []
    
    total_users = User.objects.filter(is_active=True).count()
    
    context = {
        'academic_period': current_period,
        'total_students': total_students,
        'total_lecturers': total_lecturers,
        'total_coordinators': total_coordinators,
        'total_programmes': total_programmes,
        'total_course_units': total_course_units,
        'today_lectures': today_lectures,
        'active_lectures': active_lectures,
        'total_lectures_semester': total_lectures_semester,
        'total_attendances': total_attendances,
        'total_attended': total_attended,
        'total_possible': total_possible,
        'overall_attendance': overall_attendance,
        'today_present': today_present,
        'recent_attendances': recent_attendances,
        'recent_lectures': recent_lectures,
        'total_users': total_users,
        'page_title': 'Administrator Dashboard'
    }
    return render(request, 'admin/dashboard.html', context)


# ==================== PROFILE VIEWS ====================

@login_required
def change_password_view(request):
    """
    Change password view - For first login and password changes
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if current_password:
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return render(request, 'core/change_password.html')
        
        if not new_password or len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'core/change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/change_password.html')
        
        if not re.search(r'[A-Z]', new_password):
            messages.warning(request, 'Password should contain at least one uppercase letter.')
        if not re.search(r'[a-z]', new_password):
            messages.warning(request, 'Password should contain at least one lowercase letter.')
        if not re.search(r'[0-9]', new_password):
            messages.warning(request, 'Password should contain at least one number.')
        
        request.user.set_password(new_password)
        request.user.is_verified = True
        request.user.save()
        
        user = authenticate(request, username=request.user.username, password=new_password)
        if user:
            login(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')
    
    is_first_login = not request.user.is_verified
    
    context = {
        'is_first_login': is_first_login,
        'page_title': 'Change Password'
    }
    return render(request, 'core/change_password.html', context)


@login_required
def profile_view(request):
    """
    User profile view
    """
    user = request.user
    context = {
        'user': user,
        'page_title': 'My Profile'
    }
    
    if user.role == 'student':
        try:
            student = user.student_profile
            context['student'] = student
            context['profile_type'] = 'Student'
        except Student.DoesNotExist:
            pass
    elif user.role == 'lecturer':
        try:
            lecturer = user.lecturer_profile
            context['lecturer'] = lecturer
            context['profile_type'] = 'Lecturer'
        except Lecturer.DoesNotExist:
            pass
    elif user.role == 'coordinator':
        try:
            coordinator = user.coordinator_profile
            context['coordinator'] = coordinator
            context['profile_type'] = 'Coordinator'
        except Coordinator.DoesNotExist:
            pass
    elif user.role == 'admin':
        context['profile_type'] = 'Administrator'
    
    return render(request, 'core/profile.html', context)


@login_required
def update_profile_view(request):
    """
    Update user profile
    """
    if request.method != 'POST':
        return redirect('profile')
    
    user = request.user
    
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()
    
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if email:
        user.email = email
    if phone:
        user.phone = phone
    
    user.save()
    
    messages.success(request, 'Profile updated successfully!')
    return redirect('profile')


# ==================== NOTIFICATION VIEWS ====================

@login_required
def notifications_view(request):
    """
    User notifications view
    """
    user = request.user
    notifications = user.notifications.all().order_by('-created_at')
    
    unread = notifications.filter(is_read=False)
    for notif in unread:
        notif.is_read = True
        notif.save()
    
    context = {
        'notifications': notifications,
        'page_title': 'Notifications'
    }
    return render(request, 'core/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a notification as read
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except:
        return JsonResponse({'error': 'Notification not found'}, status=404)


@login_required
def clear_notifications(request):
    """
    Clear all notifications for the user
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    request.user.notifications.all().delete()
    messages.success(request, 'All notifications cleared.')
    return redirect('notifications')


# ==================== STUDENT VIEWS ====================

@login_required
def attendance_history_view(request):
    """
    View attendance history
    """
    user = request.user
    
    if user.role != 'student':
        messages.error(request, 'Only students can view attendance history.')
        return redirect('dashboard')
    
    try:
        student = user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')
    
    period_id = request.GET.get('period')
    status_filter = request.GET.get('status')
    
    attendances = Attendance.objects.filter(student=student).select_related('lecture', 'lecture__course_unit')
    
    if period_id:
        attendances = attendances.filter(academic_period_id=period_id)
    if status_filter:
        attendances = attendances.filter(status=status_filter)
    
    attendances = attendances.order_by('-check_in_time')
    
    periods = AcademicPeriod.objects.filter(
        academic_year__is_active=True
    ).distinct()
    
    context = {
        'attendances': attendances,
        'periods': periods,
        'selected_period': period_id,
        'selected_status': status_filter,
        'page_title': 'Attendance History'
    }
    return render(request, 'student/attendance_history.html', context)


@login_required
def timetable_view(request):
    """
    View timetable
    """
    user = request.user
    
    if user.role == 'student':
        try:
            student = user.student_profile
            from timetable.models import Timetable
            timetable_entries = Timetable.objects.filter(
                programme=student.programme,
                academic_period=AcademicPeriod.objects.filter(is_current=True).first(),
                is_active=True
            ).order_by('day', 'start_time')
            
            context = {
                'timetable_entries': timetable_entries,
                'programme': student.programme,
                'page_title': 'My Timetable'
            }
            return render(request, 'student/timetable.html', context)
        except Student.DoesNotExist:
            messages.error(request, 'Student profile not found.')
            return redirect('dashboard')
    
    elif user.role == 'lecturer':
        from timetable.models import Timetable
        timetable_entries = Timetable.objects.filter(
            lecturer=user,
            academic_period=AcademicPeriod.objects.filter(is_current=True).first(),
            is_active=True
        ).order_by('day', 'start_time')
        
        context = {
            'timetable_entries': timetable_entries,
            'page_title': 'My Timetable'
        }
        return render(request, 'lecturer/timetable.html', context)
    
    else:
        messages.error(request, 'Timetable view is only available for students and lecturers.')
        return redirect('dashboard')


@login_required
def course_units_view(request):
    """
    View course units for student or lecturer
    """
    user = request.user
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    
    if user.role == 'student':
        try:
            student = user.student_profile
            course_units = CourseUnit.objects.filter(
                programme=student.programme,
                academic_period=current_period,
                is_active=True
            ).select_related('lecturer')
            
            context = {
                'course_units': course_units,
                'programme': student.programme,
                'page_title': 'My Course Units'
            }
            return render(request, 'student/course_units.html', context)
        except Student.DoesNotExist:
            messages.error(request, 'Student profile not found.')
            return redirect('dashboard')
    
    elif user.role == 'lecturer':
        course_units = CourseUnit.objects.filter(
            lecturer=user,
            academic_period=current_period,
            is_active=True
        ).select_related('programme')
        
        context = {
            'course_units': course_units,
            'page_title': 'My Course Units'
        }
        return render(request, 'lecturer/course_units.html', context)
    
    else:
        messages.error(request, 'Course units view is only available for students and lecturers.')
        return redirect('dashboard')


# ==================== ADMIN MANAGEMENT VIEWS ====================

# -------- STUDENT MANAGEMENT --------

@login_required
def admin_manage_students(request):
    """
    Admin page for managing students with bulk add
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    programmes = Programme.objects.filter(is_active=True)
    
    context = {
        'academic_period': current_period,
        'programmes': programmes,
        'page_title': 'Manage Students',
    }
    return render(request, 'admin/manage_students.html', context)


@login_required
@csrf_exempt
def admin_add_students_bulk(request):
    """
    Bulk add students
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            students_data = data.get('students', [])
            
            if not students_data:
                return JsonResponse({'error': 'No students data provided'}, status=400)
            
            current_period = AcademicPeriod.objects.filter(is_current=True).first()
            if not current_period:
                return JsonResponse({'error': 'No active academic period found'}, status=400)
            
            results = {
                'created': [],
                'errors': [],
                'total': len(students_data)
            }
            
            with transaction.atomic():
                for student_data in students_data:
                    full_name = student_data.get('full_name', '').strip()
                    registration_number = student_data.get('registration_number', '').strip()
                    programme_code = student_data.get('programme', '').strip()
                    year_of_study = student_data.get('year_of_study', 1)
                    
                    if not full_name or not registration_number or not programme_code:
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Missing required fields (full_name, registration_number, programme)'
                        })
                        continue
                    
                    if Student.objects.filter(registration_number=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Registration number ' + registration_number + ' already exists'
                        })
                        continue
                    
                    if User.objects.filter(username=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Username ' + registration_number + ' already exists'
                        })
                        continue
                    
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Programme ' + programme_code + ' not found'
                        })
                        continue
                    
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    try:
                        user = User.objects.create_user(
                            username=registration_number,
                            password=full_name,
                            first_name=first_name,
                            last_name=last_name,
                            role='student'
                        )
                        user.is_verified = False
                        user.save()
                    except Exception as e:
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Failed to create user: ' + str(e)
                        })
                        continue
                    
                    try:
                        student = Student.objects.create(
                            user=user,
                            registration_number=registration_number,
                            programme=programme,
                            academic_period=current_period,
                            year_of_study=year_of_study,
                            is_active=True
                        )
                        results['created'].append({
                            'registration_number': registration_number,
                            'full_name': full_name,
                            'programme': programme.code,
                            'year_of_study': year_of_study
                        })
                    except Exception as e:
                        user.delete()
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Failed to create student: ' + str(e)
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def admin_get_students_list(request):
    """
    Get list of all students with their details
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    students = Student.objects.select_related('user', 'programme').filter(is_active=True)
    data = []
    for student in students:
        data.append({
            'id': student.id,
            'registration_number': student.registration_number,
            'full_name': student.user.get_full_name(),
            'programme': student.programme.code,
            'programme_name': student.programme.name,
            'year_of_study': student.year_of_study,
            'is_active': student.is_active,
            'created_at': student.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'students': data})


@login_required
@csrf_exempt
def admin_delete_student(request, student_id):
    """
    Delete (soft delete) a student
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            student = get_object_or_404(Student, id=student_id)
            student.is_active = False
            student.user.is_active = False
            student.user.save()
            student.save()
            return JsonResponse({'success': True, 'message': 'Student deactivated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_activate_student(request, student_id):
    """
    Activate a student
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            student = get_object_or_404(Student, id=student_id)
            student.is_active = True
            student.user.is_active = True
            student.user.save()
            student.save()
            return JsonResponse({'success': True, 'message': 'Student activated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_reset_student_password(request, student_id):
    """
    Reset student password to their full name
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            student = get_object_or_404(Student, id=student_id)
            full_name = student.user.get_full_name()
            student.user.set_password(full_name)
            student.user.is_verified = False
            student.user.save()
            return JsonResponse({
                'success': True,
                'message': 'Password reset successfully. New password: ' + full_name
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# -------- LECTURER MANAGEMENT --------

@login_required
def admin_manage_lecturers(request):
    """
    Admin page for managing lecturers with bulk add
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    
    context = {
        'academic_period': current_period,
        'page_title': 'Manage Lecturers',
    }
    return render(request, 'admin/manage_lecturers.html', context)


@login_required
@csrf_exempt
def admin_add_lecturers_bulk(request):
    """
    Bulk add lecturers
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lecturers_data = data.get('lecturers', [])
            
            if not lecturers_data:
                return JsonResponse({'error': 'No lecturers data provided'}, status=400)
            
            current_period = AcademicPeriod.objects.filter(is_current=True).first()
            if not current_period:
                return JsonResponse({'error': 'No active academic period found'}, status=400)
            
            results = {
                'created': [],
                'errors': [],
                'total': len(lecturers_data)
            }
            
            with transaction.atomic():
                for lecturer_data in lecturers_data:
                    full_name = lecturer_data.get('full_name', '').strip()
                    staff_number = lecturer_data.get('staff_number', '').strip()
                    username = lecturer_data.get('username', '').strip()
                    password = lecturer_data.get('password', '')
                    course_units_input = lecturer_data.get('course_units', [])
                    
                    if not full_name or not staff_number:
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Missing required fields (full_name, staff_number)'
                        })
                        continue
                    
                    if not username:
                        username = staff_number.lower().replace('/', '_').replace(' ', '_')
                    
                    if Lecturer.objects.filter(staff_number=staff_number).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Staff number ' + staff_number + ' already exists'
                        })
                        continue
                    
                    if User.objects.filter(username=username).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Username ' + username + ' already exists'
                        })
                        continue
                    
                    if not password:
                        password = full_name.lower().replace(' ', '')
                        password = re.sub(r'[^a-zA-Z0-9]', '', password)
                        if len(password) < 6:
                            password = password + '123'
                    
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    try:
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            first_name=first_name,
                            last_name=last_name,
                            role='lecturer',
                            is_verified=True
                        )
                        user.save()
                    except Exception as e:
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Failed to create user: ' + str(e)
                        })
                        continue
                    
                    try:
                        lecturer = Lecturer.objects.create(
                            user=user,
                            staff_number=staff_number,
                            academic_period=current_period,
                            is_active=True
                        )
                        
                        assigned_courses = []
                        if course_units_input:
                            if isinstance(course_units_input, str):
                                course_units_input = [c.strip() for c in course_units_input.split(',') if c.strip()]
                            
                            for course_code in course_units_input:
                                try:
                                    course = CourseUnit.objects.get(code=course_code.upper(), is_active=True)
                                    course.lecturer = user
                                    course.save()
                                    assigned_courses.append(course.code)
                                except CourseUnit.DoesNotExist:
                                    pass
                        
                        results['created'].append({
                            'staff_number': staff_number,
                            'full_name': full_name,
                            'username': username,
                            'password': password,
                            'course_units': assigned_courses
                        })
                    except Exception as e:
                        user.delete()
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Failed to create lecturer: ' + str(e)
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def admin_get_lecturers_list(request):
    """
    Get list of all lecturers with their details
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    lecturers = Lecturer.objects.select_related('user').filter(is_active=True)
    data = []
    for lecturer in lecturers:
        course_units = CourseUnit.objects.filter(lecturer=lecturer.user, is_active=True)
        
        data.append({
            'id': lecturer.id,
            'staff_number': lecturer.staff_number,
            'full_name': lecturer.user.get_full_name(),
            'username': lecturer.user.username,
            'course_units': [{'code': c.code, 'name': c.name} for c in course_units],
            'course_count': course_units.count(),
            'is_active': lecturer.is_active,
            'created_at': lecturer.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'lecturers': data})


@login_required
@csrf_exempt
def admin_delete_lecturer(request, lecturer_id):
    """
    Delete (soft delete) a lecturer
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            lecturer = get_object_or_404(Lecturer, id=lecturer_id)
            lecturer.is_active = False
            lecturer.user.is_active = False
            lecturer.user.save()
            lecturer.save()
            return JsonResponse({'success': True, 'message': 'Lecturer deactivated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_activate_lecturer(request, lecturer_id):
    """
    Activate a lecturer
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            lecturer = get_object_or_404(Lecturer, id=lecturer_id)
            lecturer.is_active = True
            lecturer.user.is_active = True
            lecturer.user.save()
            lecturer.save()
            return JsonResponse({'success': True, 'message': 'Lecturer activated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_reset_lecturer_password(request, lecturer_id):
    """
    Reset lecturer password
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lecturer = get_object_or_404(Lecturer, id=lecturer_id)
            new_password = data.get('password', '')
            
            if not new_password:
                alphabet = string.ascii_letters + string.digits
                new_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            
            lecturer.user.set_password(new_password)
            lecturer.user.save()
            return JsonResponse({
                'success': True,
                'message': 'Password reset successfully',
                'new_password': new_password
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# -------- COURSE UNIT MANAGEMENT --------

@login_required
def admin_manage_course_units(request):
    """
    Admin page for managing course units with bulk add
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    programmes = Programme.objects.filter(is_active=True)
    lecturers = User.objects.filter(role='lecturer', is_active=True)
    
    context = {
        'academic_period': current_period,
        'programmes': programmes,
        'lecturers': lecturers,
        'page_title': 'Manage Course Units',
    }
    return render(request, 'admin/manage_course_units.html', context)


@login_required
@csrf_exempt
def admin_add_course_units_bulk(request):
    """
    Bulk add course units
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            course_units_data = data.get('course_units', [])
            
            if not course_units_data:
                return JsonResponse({'error': 'No course units data provided'}, status=400)
            
            current_period = AcademicPeriod.objects.filter(is_current=True).first()
            if not current_period:
                return JsonResponse({'error': 'No active academic period found'}, status=400)
            
            results = {
                'created': [],
                'errors': [],
                'total': len(course_units_data)
            }
            
            with transaction.atomic():
                for course_data in course_units_data:
                    code = course_data.get('code', '').strip().upper()
                    name = course_data.get('name', '').strip()
                    programme_code = course_data.get('programme', '').strip()
                    lecturer_username = course_data.get('lecturer', '').strip()
                    year_of_study = course_data.get('year_of_study', 1)
                    
                    if not code or not name or not programme_code:
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Missing required fields (code, name, programme)'
                        })
                        continue
                    
                    if CourseUnit.objects.filter(code=code).exists():
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Course code ' + code + ' already exists'
                        })
                        continue
                    
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Programme ' + programme_code + ' not found'
                        })
                        continue
                    
                    lecturer = None
                    if lecturer_username:
                        try:
                            lecturer = User.objects.get(username=lecturer_username, role='lecturer')
                        except User.DoesNotExist:
                            results['errors'].append({
                                'data': course_data,
                                'error': 'Lecturer ' + lecturer_username + ' not found'
                            })
                            continue
                    
                    try:
                        course_unit = CourseUnit.objects.create(
                            code=code,
                            name=name,
                            programme=programme,
                            academic_period=current_period,
                            lecturer=lecturer,
                            year_of_study=year_of_study,
                            is_active=True
                        )
                        results['created'].append({
                            'code': code,
                            'name': name,
                            'programme': programme.code,
                            'lecturer': lecturer.username if lecturer else 'Not assigned',
                            'year_of_study': year_of_study
                        })
                    except Exception as e:
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Failed to create course unit: ' + str(e)
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def admin_get_course_units_list(request):
    """
    Get list of all course units with their details
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    course_units = CourseUnit.objects.select_related('programme', 'lecturer', 'academic_period').filter(is_active=True)
    data = []
    for course in course_units:
        data.append({
            'id': course.id,
            'code': course.code,
            'name': course.name,
            'programme': course.programme.code,
            'programme_name': course.programme.name,
            'lecturer': course.lecturer.username if course.lecturer else 'Not Assigned',
            'lecturer_name': course.lecturer.get_full_name() if course.lecturer else 'Not Assigned',
            'year_of_study': course.year_of_study,
            'academic_period': str(course.academic_period),
            'is_active': course.is_active,
            'created_at': course.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'course_units': data})


@login_required
@csrf_exempt
def admin_delete_course_unit(request, course_id):
    """
    Delete (soft delete) a course unit
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            course = get_object_or_404(CourseUnit, id=course_id)
            course.is_active = False
            course.save()
            return JsonResponse({'success': True, 'message': 'Course unit deactivated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_activate_course_unit(request, course_id):
    """
    Activate a course unit
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            course = get_object_or_404(CourseUnit, id=course_id)
            course.is_active = True
            course.save()
            return JsonResponse({'success': True, 'message': 'Course unit activated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# -------- PROGRAMME MANAGEMENT --------

@login_required
def admin_manage_programmes(request):
    """
    Admin page for managing programmes
    """
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    programmes = Programme.objects.all()
    
    context = {
        'programmes': programmes,
        'page_title': 'Manage Programmes',
    }
    return render(request, 'admin/manage_programmes.html', context)


@login_required
@csrf_exempt
def admin_add_programme(request):
    """
    Add a new programme
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            code = data.get('code', '').strip().upper()
            name = data.get('name', '').strip()
            duration = data.get('duration', 4)
            session = data.get('session', 'DAY')
            
            if not code or not name:
                return JsonResponse({'error': 'Code and name are required'}, status=400)
            
            if Programme.objects.filter(code=code).exists():
                return JsonResponse({'error': 'Programme code ' + code + ' already exists'}, status=400)
            
            programme = Programme.objects.create(
                code=code,
                name=name,
                duration=duration,
                session=session,
                is_active=True
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Programme created successfully',
                'programme': {
                    'id': programme.id,
                    'code': programme.code,
                    'name': programme.name,
                    'duration': programme.duration,
                    'session': programme.session,
                    'is_active': programme.is_active
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def admin_get_programmes_list(request):
    """
    Get list of all programmes
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    programmes = Programme.objects.filter(is_active=True)
    data = [{
        'code': p.code,
        'name': p.name,
        'session': p.session,
        'duration': p.duration
    } for p in programmes]
    
    return JsonResponse({'programmes': data})


@login_required
@csrf_exempt
def admin_update_programme(request, programme_id):
    """
    Update a programme
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            programme = get_object_or_404(Programme, id=programme_id)
            
            if 'code' in data:
                code = data['code'].strip().upper()
                if Programme.objects.exclude(id=programme_id).filter(code=code).exists():
                    return JsonResponse({'error': 'Programme code ' + code + ' already exists'}, status=400)
                programme.code = code
            
            if 'name' in data:
                programme.name = data['name'].strip()
            if 'duration' in data:
                programme.duration = data['duration']
            if 'session' in data:
                programme.session = data['session']
            if 'is_active' in data:
                programme.is_active = data['is_active']
            
            programme.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Programme updated successfully',
                'programme': {
                    'id': programme.id,
                    'code': programme.code,
                    'name': programme.name,
                    'duration': programme.duration,
                    'session': programme.session,
                    'is_active': programme.is_active
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_delete_programme(request, programme_id):
    """
    Delete (soft delete) a programme
    """
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            programme = get_object_or_404(Programme, id=programme_id)
            programme.is_active = False
            programme.save()
            return JsonResponse({'success': True, 'message': 'Programme deactivated successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# -------- LECTURE MANAGEMENT --------

@login_required
def admin_manage_lectures(request):
    """
    Admin page for managing lectures with room coordinates
    """
    if request.user.role not in ['admin', 'lecturer']:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    programmes = Programme.objects.filter(is_active=True)
    course_units = CourseUnit.objects.filter(is_active=True)
    lecturers = User.objects.filter(role='lecturer', is_active=True)
    
    if current_period:
        lectures = Lecture.objects.filter(
            academic_period=current_period
        ).select_related('course_unit', 'lecturer', 'programme').order_by('-scheduled_date', 'start_time')
    else:
        lectures = Lecture.objects.none()
    
    today = datetime.now().date()
    
    context = {
        'academic_period': current_period,
        'programmes': programmes,
        'course_units': course_units,
        'lecturers': lecturers,
        'lectures': lectures,
        'today': today,
        'page_title': 'Manage Lectures',
    }
    return render(request, 'admin/manage_lectures.html', context)


@login_required
@csrf_exempt
def admin_add_lecture(request):
    """
    Add a single lecture with room coordinates
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Get or create academic period
            academic_year_id = data.get('academic_year')
            semester_id = data.get('semester')
            
            if not academic_year_id or not semester_id:
                return JsonResponse({'error': 'Academic year and semester are required'}, status=400)
            
            try:
                academic_year = AcademicYear.objects.get(id=academic_year_id)
                semester = Semester.objects.get(id=semester_id)
                academic_period, created = AcademicPeriod.objects.get_or_create(
                    academic_year=academic_year,
                    semester=semester,
                    defaults={'is_current': False}
                )
            except (AcademicYear.DoesNotExist, Semester.DoesNotExist) as e:
                return JsonResponse({'error': str(e)}, status=400)
            
            # Get course unit
            try:
                course_unit = CourseUnit.objects.get(id=data.get('course_unit'))
            except CourseUnit.DoesNotExist:
                return JsonResponse({'error': 'Course unit not found'}, status=400)
            
            # Get lecturer
            lecturer_id = data.get('lecturer')
            if lecturer_id:
                try:
                    lecturer = User.objects.get(id=lecturer_id, role='lecturer')
                except User.DoesNotExist:
                    return JsonResponse({'error': 'Lecturer not found'}, status=400)
            else:
                lecturer = course_unit.lecturer
                if not lecturer:
                    return JsonResponse({'error': 'Course unit has no lecturer assigned'}, status=400)
            
            # Get programme
            programme_id = data.get('programme')
            if programme_id:
                try:
                    programme = Programme.objects.get(id=programme_id)
                except Programme.DoesNotExist:
                    return JsonResponse({'error': 'Programme not found'}, status=400)
            else:
                programme = course_unit.programme
            
            # Create lecture
            lecture = Lecture.objects.create(
                course_unit=course_unit,
                lecturer=lecturer,
                academic_period=academic_period,
                programme=programme,
                title=data.get('title'),
                lecture_type=data.get('lecture_type', 'PHYSICAL'),
                status='scheduled',
                scheduled_date=data.get('scheduled_date'),
                start_time=data.get('start_time'),
                end_time=data.get('end_time'),
                location=data.get('location', ''),
                room_latitude=data.get('room_latitude'),
                room_longitude=data.get('room_longitude'),
                room_radius=data.get('room_radius', 50),
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Lecture created successfully!',
                'lecture_id': lecture.id,
                'lecture': {
                    'id': lecture.id,
                    'title': lecture.title,
                    'course_unit': lecture.course_unit.code,
                    'lecturer': lecture.lecturer.get_full_name(),
                    'lecture_type': lecture.get_lecture_type_display(),
                    'scheduled_date': lecture.scheduled_date.strftime('%Y-%m-%d'),
                    'start_time': lecture.start_time.strftime('%H:%M'),
                    'end_time': lecture.end_time.strftime('%H:%M'),
                    'location': lecture.location,
                    'has_coordinates': bool(lecture.room_latitude and lecture.room_longitude),
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_add_lectures_bulk(request):
    """
    Bulk add lectures with room coordinates
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lectures_data = data.get('lectures', [])
            
            if not lectures_data:
                return JsonResponse({'error': 'No lectures data provided'}, status=400)
            
            current_period = AcademicPeriod.objects.filter(is_current=True).first()
            if not current_period:
                return JsonResponse({'error': 'No active academic period found'}, status=400)
            
            results = {
                'created': [],
                'errors': [],
                'total': len(lectures_data)
            }
            
            with transaction.atomic():
                for lecture_data in lectures_data:
                    course_unit_code = lecture_data.get('course_unit', '').strip()
                    lecturer_username = lecture_data.get('lecturer', '').strip()
                    programme_code = lecture_data.get('programme', '').strip()
                    title = lecture_data.get('title', '').strip()
                    lecture_type = lecture_data.get('lecture_type', 'PHYSICAL')
                    scheduled_date = lecture_data.get('scheduled_date')
                    start_time = lecture_data.get('start_time')
                    end_time = lecture_data.get('end_time')
                    location = lecture_data.get('location', '')
                    room_latitude = lecture_data.get('room_latitude')
                    room_longitude = lecture_data.get('room_longitude')
                    room_radius = lecture_data.get('room_radius', 50)
                    
                    # Validate required fields
                    if not all([course_unit_code, title, scheduled_date, start_time, end_time]):
                        results['errors'].append({
                            'data': lecture_data,
                            'error': 'Missing required fields (course_unit, title, scheduled_date, start_time, end_time)'
                        })
                        continue
                    
                    # Get course unit
                    try:
                        course_unit = CourseUnit.objects.get(code=course_unit_code, is_active=True)
                    except CourseUnit.DoesNotExist:
                        results['errors'].append({
                            'data': lecture_data,
                            'error': 'Course unit ' + course_unit_code + ' not found'
                        })
                        continue
                    
                    # Get programme
                    if programme_code:
                        try:
                            programme = Programme.objects.get(code=programme_code)
                        except Programme.DoesNotExist:
                            results['errors'].append({
                                'data': lecture_data,
                                'error': 'Programme ' + programme_code + ' not found'
                            })
                            continue
                    else:
                        programme = course_unit.programme
                    
                    # Get lecturer
                    lecturer = course_unit.lecturer
                    if lecturer_username:
                        try:
                            lecturer = User.objects.get(username=lecturer_username, role='lecturer')
                        except User.DoesNotExist:
                            results['errors'].append({
                                'data': lecture_data,
                                'error': 'Lecturer ' + lecturer_username + ' not found'
                            })
                            continue
                    
                    if not lecturer:
                        results['errors'].append({
                            'data': lecture_data,
                            'error': 'No lecturer assigned to this course unit'
                        })
                        continue
                    
                    try:
                        # Parse date and time
                        if isinstance(scheduled_date, str):
                            scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                        if isinstance(start_time, str):
                            start_time = datetime.strptime(start_time, '%H:%M').time()
                        if isinstance(end_time, str):
                            end_time = datetime.strptime(end_time, '%H:%M').time()
                        
                        lecture = Lecture.objects.create(
                            course_unit=course_unit,
                            lecturer=lecturer,
                            academic_period=current_period,
                            programme=programme,
                            title=title,
                            lecture_type=lecture_type,
                            status='scheduled',
                            scheduled_date=scheduled_date,
                            start_time=start_time,
                            end_time=end_time,
                            location=location,
                            room_latitude=room_latitude,
                            room_longitude=room_longitude,
                            room_radius=room_radius,
                        )
                        
                        results['created'].append({
                            'id': lecture.id,
                            'title': lecture.title,
                            'course_unit': course_unit.code,
                            'lecturer': lecturer.get_full_name(),
                            'date': scheduled_date.strftime('%Y-%m-%d'),
                            'type': lecture_type,
                            'has_coordinates': bool(room_latitude and room_longitude)
                        })
                    except Exception as e:
                        results['errors'].append({
                            'data': lecture_data,
                            'error': 'Failed to create lecture: ' + str(e)
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_update_lecture(request, lecture_id):
    """
    Update lecture details including room coordinates
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lecture = get_object_or_404(Lecture, id=lecture_id)
            
            if 'title' in data:
                lecture.title = data['title']
            if 'lecture_type' in data:
                lecture.lecture_type = data['lecture_type']
            if 'scheduled_date' in data:
                lecture.scheduled_date = data['scheduled_date']
            if 'start_time' in data:
                lecture.start_time = data['start_time']
            if 'end_time' in data:
                lecture.end_time = data['end_time']
            if 'location' in data:
                lecture.location = data['location']
            if 'room_latitude' in data:
                lecture.room_latitude = data['room_latitude']
            if 'room_longitude' in data:
                lecture.room_longitude = data['room_longitude']
            if 'room_radius' in data:
                lecture.room_radius = data['room_radius']
            
            if 'course_unit' in data:
                try:
                    course_unit = CourseUnit.objects.get(id=data['course_unit'])
                    lecture.course_unit = course_unit
                    lecture.programme = course_unit.programme
                except CourseUnit.DoesNotExist:
                    return JsonResponse({'error': 'Course unit not found'}, status=400)
            
            if 'lecturer' in data:
                try:
                    lecturer = User.objects.get(id=data['lecturer'], role='lecturer')
                    lecture.lecturer = lecturer
                except User.DoesNotExist:
                    return JsonResponse({'error': 'Lecturer not found'}, status=400)
            
            lecture.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Lecture updated successfully!',
                'lecture': {
                    'id': lecture.id,
                    'title': lecture.title,
                    'course_unit': lecture.course_unit.code,
                    'lecturer': lecture.lecturer.get_full_name(),
                    'lecture_type': lecture.get_lecture_type_display(),
                    'scheduled_date': lecture.scheduled_date.strftime('%Y-%m-%d'),
                    'start_time': lecture.start_time.strftime('%H:%M'),
                    'end_time': lecture.end_time.strftime('%H:%M'),
                    'location': lecture.location,
                    'room_latitude': float(lecture.room_latitude) if lecture.room_latitude else None,
                    'room_longitude': float(lecture.room_longitude) if lecture.room_longitude else None,
                    'room_radius': lecture.room_radius,
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def admin_delete_lecture(request, lecture_id):
    """
    Delete (soft delete) a lecture
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            lecture = get_object_or_404(Lecture, id=lecture_id)
            lecture.status = 'cancelled'
            lecture.save()
            return JsonResponse({'success': True, 'message': 'Lecture cancelled successfully!'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ============================================================================
# IMPORTANT: THIS IS THE FIXED FUNCTION - admin_get_lecture_detail
# This function allows students to access lecture coordinates for attendance
# ============================================================================

@login_required
def admin_get_lecture_detail(request, lecture_id):
    """
    Get lecture details - Accessible by:
    - Admin: Full access
    - Lecturer: Their own lectures
    - Student: Room coordinates for attendance (REQUIRED for attendance to work)
    """
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        # Get the lecture
        lecture = Lecture.objects.select_related('course_unit', 'lecturer', 'programme', 'academic_period').get(id=lecture_id)
        
        # ROLE-BASED ACCESS CONTROL
        user_role = request.user.role
        
        # ADMIN - Full access to all lectures
        if user_role == 'admin':
            # Admin has full access
            pass
            
        # LECTURER - Can only access their own lectures
        elif user_role == 'lecturer':
            if lecture.lecturer != request.user:
                return JsonResponse(
                    {'error': 'You can only view your own lectures'}, 
                    status=403
                )
        
        # STUDENT - Can access lecture details for attendance
        elif user_role == 'student':
            try:
                student = request.user.student_profile
                # Check if student is enrolled in this course/programme
                if student.programme != lecture.programme:
                    return JsonResponse(
                        {'error': 'You are not enrolled in this course. Your programme: ' + student.programme.code + ', Lecture programme: ' + lecture.programme.code}, 
                        status=403
                    )
            except Student.DoesNotExist:
                return JsonResponse(
                    {'error': 'Student profile not found'}, 
                    status=403
                )
            
            # STUDENT: Return limited data (only what's needed for attendance)
            return JsonResponse({
                'lecture': {
                    'id': lecture.id,
                    'title': lecture.title,
                    'lecture_type': lecture.lecture_type,
                    'location': lecture.location,
                    'room_latitude': float(lecture.room_latitude) if lecture.room_latitude else '',
                    'room_longitude': float(lecture.room_longitude) if lecture.room_longitude else '',
                    'room_radius': lecture.room_radius if lecture.room_radius else 50,
                    'status': lecture.status,
                    'scheduled_date': lecture.scheduled_date.strftime('%Y-%m-%d'),
                    'start_time': lecture.start_time.strftime('%H:%M'),
                    'end_time': lecture.end_time.strftime('%H:%M'),
                }
            })
        
        # UNKNOWN ROLE
        else:
            return JsonResponse(
                {'error': 'Permission denied. Unknown user role: ' + str(user_role)}, 
                status=403
            )
        
        # ADMIN & LECTURER: Return full data
        return JsonResponse({
            'lecture': {
                'id': lecture.id,
                'title': lecture.title,
                'course_unit': lecture.course_unit.id,
                'course_unit_code': lecture.course_unit.code,
                'course_unit_name': lecture.course_unit.name,
                'lecturer': lecture.lecturer.id,
                'lecturer_name': lecture.lecturer.get_full_name(),
                'programme': lecture.programme.id,
                'programme_code': lecture.programme.code,
                'academic_period': lecture.academic_period.id,
                'lecture_type': lecture.lecture_type,
                'scheduled_date': lecture.scheduled_date.strftime('%Y-%m-%d'),
                'start_time': lecture.start_time.strftime('%H:%M'),
                'end_time': lecture.end_time.strftime('%H:%M'),
                'location': lecture.location,
                'room_latitude': float(lecture.room_latitude) if lecture.room_latitude else '',
                'room_longitude': float(lecture.room_longitude) if lecture.room_longitude else '',
                'room_radius': lecture.room_radius if lecture.room_radius else 50,
                'status': lecture.status,
            }
        })
        
    except Lecture.DoesNotExist:
        return JsonResponse(
            {'error': 'Lecture not found'}, 
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'error': str(e)}, 
            status=500
        )


# ============================================================================
# END OF FIXED FUNCTION
# ============================================================================


@login_required
def admin_get_lectures_list(request):
    """
    Get list of all lectures with room coordinates
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    
    if current_period:
        lectures = Lecture.objects.filter(
            academic_period=current_period
        ).select_related('course_unit', 'lecturer', 'programme').order_by('-scheduled_date', 'start_time')
    else:
        lectures = Lecture.objects.none()
    
    data = []
    for lecture in lectures:
        data.append({
            'id': lecture.id,
            'title': lecture.title,
            'course_unit': lecture.course_unit.code,
            'course_unit_id': lecture.course_unit.id,
            'lecturer_name': lecture.lecturer.get_full_name(),
            'lecturer_id': lecture.lecturer.id,
            'programme': lecture.programme.code if lecture.programme else '',
            'lecture_type': lecture.lecture_type,
            'status': lecture.status,
            'scheduled_date': lecture.scheduled_date.strftime('%Y-%m-%d'),
            'start_time': lecture.start_time.strftime('%H:%M'),
            'end_time': lecture.end_time.strftime('%H:%M'),
            'location': lecture.location,
            'room_latitude': float(lecture.room_latitude) if lecture.room_latitude else None,
            'room_longitude': float(lecture.room_longitude) if lecture.room_longitude else None,
            'room_radius': lecture.room_radius,
            'has_coordinates': bool(lecture.room_latitude and lecture.room_longitude),
            'verification_code': lecture.verification_code,
            'created_at': lecture.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return JsonResponse({'lectures': data})


# ==================== HEALTH CHECK ====================

def health_check(request):
    """
    Health check endpoint for Render and monitoring
    """
    return JsonResponse({
        'status': 'ok',
        'message': 'UICT-ESAS is running',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })


# ==================== ERROR HANDLERS ====================

def handler404(request, exception):
    """
    Custom 404 error handler
    """
    return render(request, '404.html', status=404)


def handler500(request):
    """
    Custom 500 error handler
    """
    return render(request, '500.html', status=500)


def handler403(request, exception):
    """
    Custom 403 error handler
    """
    return render(request, '403.html', status=403)