from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib.auth import get_user_model
from students.models import Student
from lecturers.models import Lecturer
from coordinators.models import Coordinator
from courses.models import CourseUnit
from programmes.models import Programme
from academics.models import AcademicPeriod
import json
import re

User = get_user_model()

@login_required
def admin_manage_students(request):
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
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    if Student.objects.filter(registration_number=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': f'Registration number {registration_number} already exists'
                        })
                        continue
                    
                    if User.objects.filter(username=registration_number).exists():
                        results['errors'].append({
                            'data': student_data,
                            'error': f'Username {registration_number} already exists'
                        })
                        continue
                    
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': student_data,
                            'error': f'Programme {programme_code} not found'
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
                            'error': f'Failed to create user: {str(e)}'
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
                            'error': f'Failed to create student: {str(e)}'
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def admin_manage_lecturers(request):
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
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    if not username:
                        username = staff_number.lower().replace('/', '_').replace(' ', '_')
                    
                    if Lecturer.objects.filter(staff_number=staff_number).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': f'Staff number {staff_number} already exists'
                        })
                        continue
                    
                    if User.objects.filter(username=username).exists():
                        results['errors'].append({
                            'data': lecturer_data,
                            'error': f'Username {username} already exists'
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
                            'error': f'Failed to create user: {str(e)}'
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
                            'error': f'Failed to create lecturer: {str(e)}'
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def admin_manage_course_units(request):
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
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    if CourseUnit.objects.filter(code=code).exists():
                        results['errors'].append({
                            'data': course_data,
                            'error': f'Course code {code} already exists'
                        })
                        continue
                    
                    try:
                        programme = Programme.objects.get(code=programme_code)
                    except Programme.DoesNotExist:
                        results['errors'].append({
                            'data': course_data,
                            'error': f'Programme {programme_code} not found'
                        })
                        continue
                    
                    lecturer = None
                    if lecturer_username:
                        try:
                            lecturer = User.objects.get(username=lecturer_username, role='lecturer')
                        except User.DoesNotExist:
                            results['errors'].append({
                                'data': course_data,
                                'error': f'Lecturer {lecturer_username} not found'
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
                            'error': f'Failed to create course unit: {str(e)}'
                        })
            
            return JsonResponse(results)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def admin_get_students_list(request):
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
def admin_get_lecturers_list(request):
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
def admin_get_course_units_list(request):
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
def admin_get_programmes_list(request):
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