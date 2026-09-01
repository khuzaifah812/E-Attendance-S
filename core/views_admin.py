from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from students.models import Student
from lecturers.models import Lecturer
from coordinators.models import Coordinator
from courses.models import CourseUnit
from programmes.models import Programme
from academics.models import AcademicPeriod, AcademicYear, Semester
from lectures.models import Lecture
from timetable.models import Timetable
import json
import re
from datetime import datetime, timedelta

User = get_user_model()


# ==================== STUDENT MANAGEMENT ====================

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
                    
                    # Validate required fields
                    if not full_name or not registration_number or not programme_code:
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Missing required fields (full_name, registration_number, programme)'
                        })
                        continue
                    
                    # Check if registration number already exists
                    if Student.objects.filter(registration_number=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Registration number ' + registration_number + ' already exists'
                        })
                        continue
                    
                    # Check if username already exists
                    if User.objects.filter(username=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Username ' + registration_number + ' already exists'
                        })
                        continue
                    
                    # Get or create programme
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': student_data,
                            'error': 'Programme ' + programme_code + ' not found'
                        })
                        continue
                    
                    # Parse name
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    # Create user
                    try:
                        user = User.objects.create_user(
                            username=registration_number,
                            password=full_name,  # Default password is full name
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
                    
                    # Create student
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
                        # Rollback user creation
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


# ==================== LECTURER MANAGEMENT ====================

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
                    
                    # Validate required fields
                    if not full_name or not staff_number:
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Missing required fields (full_name, staff_number)'
                        })
                        continue
                    
                    # Generate username if not provided
                    if not username:
                        username = staff_number.lower().replace('/', '_').replace(' ', '_')
                    
                    # Check if staff number already exists
                    if Lecturer.objects.filter(staff_number=staff_number).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Staff number ' + staff_number + ' already exists'
                        })
                        continue
                    
                    # Check if username already exists
                    if User.objects.filter(username=username).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': 'Username ' + username + ' already exists'
                        })
                        continue
                    
                    # Generate password if not provided
                    if not password:
                        password = full_name.lower().replace(' ', '')
                        # Remove any special characters from password
                        password = re.sub(r'[^a-zA-Z0-9]', '', password)
                        if len(password) < 6:
                            password = password + '123'
                    
                    # Parse name
                    name_parts = full_name.split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    # Create user
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
                    
                    # Create lecturer
                    try:
                        lecturer = Lecturer.objects.create(
                            user=user,
                            staff_number=staff_number,
                            academic_period=current_period,
                            is_active=True
                        )
                        
                        # Assign course units if provided
                        assigned_courses = []
                        if course_units_input:
                            if isinstance(course_units_input, str):
                                course_units_input = [c.strip() for c in course_units_input.split(',') if c.strip()]
                            
                            for course_code in course_units_input:
                                try:
                                    course = CourseUnit.objects.get(code=course_code.upper(), is_active=True)
                                    # Update course lecturer
                                    course.lecturer = user
                                    course.save()
                                    assigned_courses.append(course.code)
                                except CourseUnit.DoesNotExist:
                                    # Log error but continue
                                    pass
                        
                        results['created'].append({
                            'staff_number': staff_number,
                            'full_name': full_name,
                            'username': username,
                            'password': password,
                            'course_units': assigned_courses
                        })
                    except Exception as e:
                        # Rollback user creation
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
        # Get course units taught by this lecturer
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
                # Generate random password
                import secrets
                import string
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


# ==================== COURSE UNIT MANAGEMENT ====================

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
                    
                    # Validate required fields
                    if not code or not name or not programme_code:
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Missing required fields (code, name, programme)'
                        })
                        continue
                    
                    # Check if course code already exists
                    if CourseUnit.objects.filter(code=code).exists():
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Course code ' + code + ' already exists'
                        })
                        continue
                    
                    # Get programme
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': course_data,
                            'error': 'Programme ' + programme_code + ' not found'
                        })
                        continue
                    
                    # Get lecturer
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
                    
                    # Create course unit
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


# ==================== PROGRAMME MANAGEMENT ====================

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
    
    programmes = Programme.objects.all()
    data = [{
        'id': p.id,
        'code': p.code,
        'name': p.name,
        'session': p.session,
        'duration': p.duration,
        'is_active': p.is_active
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


# ==================== LECTURE MANAGEMENT ====================

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
    
    # Get lectures for the current period
    if current_period:
        lectures = Lecture.objects.filter(
            academic_period=current_period
        ).select_related('course_unit', 'lecturer', 'programme').order_by('-scheduled_date', 'start_time')
    else:
        lectures = Lecture.objects.none()
    
    # Get today's date for default
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
            
            # Get lecturer (if not the course unit's lecturer, use the selected one)
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
            
            # Update fields
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
            
            # Update course unit if changed
            if 'course_unit' in data:
                try:
                    course_unit = CourseUnit.objects.get(id=data['course_unit'])
                    lecture.course_unit = course_unit
                    # Update programme to match course unit
                    lecture.programme = course_unit.programme
                except CourseUnit.DoesNotExist:
                    return JsonResponse({'error': 'Course unit not found'}, status=400)
            
            # Update lecturer if changed
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


@login_required
def admin_get_lecture_detail(request, lecture_id):
    """
    Get lecture details for editing
    """
    if request.user.role not in ['admin', 'lecturer']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        lecture = Lecture.objects.select_related('course_unit', 'lecturer', 'programme', 'academic_period').get(id=lecture_id)
        
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
                'room_radius': lecture.room_radius,
                'status': lecture.status,
            }
        })
    except Lecture.DoesNotExist:
        return JsonResponse({'error': 'Lecture not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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