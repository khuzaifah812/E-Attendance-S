from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from students.models import Student
from academics.models import AcademicPeriod
from attendance.models import Attendance
from lectures.models import Lecture
from courses.models import CourseUnit
from programmes.models import Programme
from coordinators.models import Coordinator
from lecturers.models import Lecturer
from django.contrib.auth import get_user_model
import json
import re

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from lecturers.models import Lecturer
from students.models import Student
from courses.models import CourseUnit

@staff_member_required
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')

@staff_member_required
def manage_lecturers(request):
    lecturers = Lecturer.objects.all()
    return render(request, 'admin/manage_lecturers.html', {'lecturers': lecturers})

@staff_member_required
def manage_students(request):
    students = Student.objects.all()
    return render(request, 'admin/manage_students.html', {'students': students})

@staff_member_required
def manage_course_units(request):
    units = CourseUnit.objects.all()
    return render(request, 'admin/manage_course_units.html', {'units': units})

User = get_user_model()


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
    
    # Get attendance statistics
    if current_period:
        attendances = Attendance.objects.filter(
            student=student,
            academic_period=current_period
        )
    else:
        attendances = Attendance.objects.none()
    
    total_lectures = attendances.count()
    present = attendances.filter(status='present').count()
    absent = attendances.filter(status='absent').count()
    late = attendances.filter(status='late').count()
    
    # Calculate attendance percentage
    if total_lectures > 0:
        attendance_percentage = (present / total_lectures) * 100
    else:
        attendance_percentage = 0
    
    # Get today's lectures
    today = timezone.now().date()
    if current_period:
        today_lectures = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date=today
        ).order_by('start_time')
        
        # Check if student has already attended each lecture
        for lecture in today_lectures:
            lecture.has_attended = Attendance.objects.filter(
                student=student,
                lecture=lecture
            ).exists()
    else:
        today_lectures = []
    
    # Get active lecture
    active_lecture = None
    if current_period:
        active_lecture = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date=today,
            status='active'
        ).first()
    
    # Get upcoming lectures (next 7 days)
    next_week = today + timezone.timedelta(days=7)
    if current_period:
        upcoming_lectures = Lecture.objects.filter(
            course_unit__programme=student.programme,
            academic_period=current_period,
            scheduled_date__gt=today,
            scheduled_date__lte=next_week,
            status='scheduled'
        ).order_by('scheduled_date', 'start_time')[:5]
    else:
        upcoming_lectures = []
    
    # Get attendance history (last 10)
    attendance_history = attendances.select_related('lecture', 'lecture__course_unit').order_by('-check_in_time')[:10]
    
    context = {
        'student': student,
        'academic_period': current_period,
        'total_lectures': total_lectures,
        'present': present,
        'absent': absent,
        'late': late,
        'attendance_percentage': attendance_percentage,
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
    # Check if user is a lecturer
    try:
        lecturer_profile = request.user.lecturer_profile
    except Lecturer.DoesNotExist:
        messages.error(request, 'Lecturer profile not found. Please contact the administrator.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    today = timezone.now().date()
    
    if current_period:
        # Get today's lectures
        today_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date=today
        ).order_by('start_time')
        
        # Get assigned courses
        assigned_courses = CourseUnit.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            is_active=True
        )
        
        # Get active lecture
        active_lecture = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date=today,
            status='active'
        ).first()
        
        # Get upcoming lectures (next 7 days)
        next_week = today + timezone.timedelta(days=7)
        upcoming_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date__gt=today,
            scheduled_date__lte=next_week,
            status='scheduled'
        ).order_by('scheduled_date', 'start_time')[:10]
        
        # Get recent lectures (last 5)
        recent_lectures = Lecture.objects.filter(
            lecturer=request.user,
            academic_period=current_period,
            scheduled_date__lt=today
        ).order_by('-scheduled_date', '-start_time')[:5]
        
        # Get attendance statistics for today's active lecture
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
    # Check if user is a coordinator
    try:
        coordinator_profile = request.user.coordinator_profile
    except Coordinator.DoesNotExist:
        messages.error(request, 'Coordinator profile not found. Please contact the administrator.')
        return redirect('dashboard')
    
    current_period = AcademicPeriod.objects.filter(is_current=True).first()
    today = timezone.now().date()
    
    # Get statistics
    total_students = Student.objects.filter(is_active=True).count()
    total_lecturers = User.objects.filter(role='lecturer', is_active=True).count()
    total_programmes = Programme.objects.filter(is_active=True).count()
    total_course_units = CourseUnit.objects.filter(is_active=True).count()
    
    # Get today's lectures
    today_lectures = Lecture.objects.filter(
        scheduled_date=today
    ).count() if current_period else 0
    
    # Get active lectures
    active_lectures = Lecture.objects.filter(
        status='active'
    ).count() if current_period else 0
    
    # Get attendance statistics for today
    today_attendance = Attendance.objects.filter(
        academic_period=current_period,
        check_in_time__date=today
    ) if current_period else Attendance.objects.none()
    
    today_present = today_attendance.filter(status='present').count()
    today_absent = today_attendance.filter(status='absent').count()
    
    # Get overall attendance percentage
    total_attendances = Attendance.objects.filter(
        academic_period=current_period
    ).count() if current_period else 0
    
    # Get recent attendance records
    recent_attendances = Attendance.objects.filter(
        academic_period=current_period
    ).select_related('student', 'student__user', 'lecture', 'lecture__course_unit').order_by('-check_in_time')[:20] if current_period else []
    
    context = {
        'coordinator_profile': coordinator_profile,
        'academic_period': current_period,
        'total_students': total_students,
        'total_lecturers': total_lecturers,
        'total_programmes': total_programmes,
        'total_course_units': total_course_units,
        'today_lectures': today_lectures,
        'active_lectures': active_lectures,
        'today_present': today_present,
        'today_absent': today_absent,
        'total_attendances': total_attendances,
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
    
    # Get statistics
    total_students = Student.objects.filter(is_active=True).count()
    total_lecturers = User.objects.filter(role='lecturer', is_active=True).count()
    total_coordinators = User.objects.filter(role='coordinator', is_active=True).count()
    total_programmes = Programme.objects.filter(is_active=True).count()
    total_course_units = CourseUnit.objects.filter(is_active=True).count()
    
    # Get lecture statistics
    today_lectures = Lecture.objects.filter(scheduled_date=today).count()
    active_lectures = Lecture.objects.filter(status='active').count()
    total_lectures = Lecture.objects.filter(academic_period=current_period).count() if current_period else 0
    
    # Get attendance statistics
    total_attendances = Attendance.objects.filter(
        academic_period=current_period
    ).count() if current_period else 0
    
    # Get today's attendance
    today_attendances = Attendance.objects.filter(
        check_in_time__date=today
    ) if current_period else Attendance.objects.none()
    today_present = today_attendances.filter(status='present').count()
    
    # Get recent activity
    recent_attendances = Attendance.objects.filter(
        academic_period=current_period
    ).select_related('student', 'student__user', 'lecture').order_by('-check_in_time')[:15] if current_period else []
    
    # Get recent lectures
    recent_lectures = Lecture.objects.filter(
        academic_period=current_period
    ).order_by('-scheduled_date', '-start_time')[:10] if current_period else []
    
    # Get system stats
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
        'total_lectures': total_lectures,
        'total_attendances': total_attendances,
        'today_present': today_present,
        'recent_attendances': recent_attendances,
        'recent_lectures': recent_lectures,
        'total_users': total_users,
        'page_title': 'Administrator Dashboard'
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
def change_password_view(request):
    """
    Change password view - For first login and password changes
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Check current password
        if current_password:
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return render(request, 'core/change_password.html')
        
        # Validate new password
        if not new_password or len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'core/change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/change_password.html')
        
        # Check password strength
        if not re.search(r'[A-Z]', new_password):
            messages.warning(request, 'Password should contain at least one uppercase letter.')
        if not re.search(r'[a-z]', new_password):
            messages.warning(request, 'Password should contain at least one lowercase letter.')
        if not re.search(r'[0-9]', new_password):
            messages.warning(request, 'Password should contain at least one number.')
        
        # Change password
        request.user.set_password(new_password)
        request.user.is_verified = True
        request.user.save()
        
        # Re-authenticate user
        user = authenticate(request, username=request.user.username, password=new_password)
        if user:
            login(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('dashboard')
    
    # Check if user needs to change password (first login)
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
    
    # Update user fields
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


@login_required
def notifications_view(request):
    """
    User notifications view
    """
    user = request.user
    notifications = user.notifications.all().order_by('-created_at')
    
    # Mark all as read
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
    
    # Get filters from request
    period_id = request.GET.get('period')
    status_filter = request.GET.get('status')
    
    # Base queryset
    attendances = Attendance.objects.filter(student=student).select_related('lecture', 'lecture__course_unit')
    
    # Apply filters
    if period_id:
        attendances = attendances.filter(academic_period_id=period_id)
    if status_filter:
        attendances = attendances.filter(status=status_filter)
    
    # Order by most recent
    attendances = attendances.order_by('-check_in_time')
    
    # Get available academic periods for filter
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
            # Get timetable for student's programme
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
        # Get timetable for lecturer
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


# Health check endpoint
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


# Error handlers
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