from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from academics.models import AcademicYear, Semester, AcademicPeriod
from programmes.models import Programme
from students.models import Student
from lecturers.models import Lecturer
from courses.models import CourseUnit
from lectures.models import Lecture
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed demo data for UICT-ESAS'
    
    def handle(self, *args, **options):
        self.stdout.write('=' * 60)
        self.stdout.write('Seeding demo data for UICT E-Attendance System...')
        self.stdout.write('=' * 60)
        
        # Create admin
        admin_user, created = User.objects.get_or_create(
            username='khuzaifah',
            defaults={
                'first_name': 'Admin',
                'last_name': 'User',
                'email': 'admin@uict.ac.ug',
                'role': 'admin',
                'is_superuser': True,
                'is_staff': True,
                'is_active': True,
                'is_verified': True,
            }
        )
        if created:
            admin_user.set_password('kamcoder812')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Created admin: khuzaifah'))
        
        # Create academic year
        academic_year, created = AcademicYear.objects.get_or_create(
            year='2025/2026',
            defaults={
                'start_date': datetime.date(2025, 8, 1),
                'end_date': datetime.date(2026, 7, 31),
                'is_active': True,
            }
        )
        self.stdout.write(f'✓ Academic year: {academic_year}')
        
        # Create semester
        semester, created = Semester.objects.get_or_create(
            academic_year=academic_year,
            name='1',
            defaults={
                'start_date': datetime.date(2025, 8, 15),
                'end_date': datetime.date(2025, 12, 15),
                'is_active': True,
            }
        )
        self.stdout.write(f'✓ Semester: {semester}')
        
        # Create academic period
        period, created = AcademicPeriod.objects.get_or_create(
            academic_year=academic_year,
            semester=semester,
            defaults={'is_current': True}
        )
        self.stdout.write(f'✓ Academic period: {period}')
        
        # Create programmes
        programmes_data = [
            {'code': 'DSWE', 'name': 'Diploma in Software Engineering', 'duration': 4, 'session': 'DAY'},
            {'code': 'DCS', 'name': 'Diploma in Computer Science', 'duration': 4, 'session': 'DAY'},
        ]
        
        for prog_data in programmes_data:
            programme, created = Programme.objects.get_or_create(
                code=prog_data['code'],
                defaults={
                    'name': prog_data['name'],
                    'duration': prog_data['duration'],
                    'session': prog_data['session'],
                    'is_active': True,
                }
            )
            self.stdout.write(f'✓ Programme: {programme}')
        
        dswe = Programme.objects.get(code='DSWE')
        
        # Create students
        students_data = [
            {'name': 'AINE MBABAZI KHUZAIFAH', 'reg': 'UICT/2025/DSWE/DAY/2246'},
            {'name': 'BARAKA RODGERS', 'reg': 'UICT/2025/DSWE/DAY/1595'},
            {'name': 'ATURINDA SYLONE', 'reg': 'UICT/2025/DSWE/DAY/2610'},
            {'name': 'TURYAMUHAKI RODGERS', 'reg': 'UICT/2025/DSWE/DAY/1638'},
            {'name': 'ALOKO PEACE', 'reg': 'UICT/2025/DSWE/DAY/1639'},
            {'name': 'AGABA BENJAMIN', 'reg': 'UICT/2025/DSWE/DAY/2510'},
            {'name': 'MUHINDO SIMON', 'reg': 'UICT/2025/DSWE/DAY/1583'},
            {'name': 'NABAGESERA AIDAH RUTH', 'reg': 'UICT/2025/DSWE/DAY/1568'},
        ]
        
        for student_data in students_data:
            username = student_data['reg']
            name_parts = student_data['name'].split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'student',
                    'is_active': True,
                }
            )
            if created:
                user.set_password(student_data['name'])
                user.save()
                self.stdout.write(f'✓ Created student: {username}')
            
            student, created = Student.objects.get_or_create(
                user=user,
                defaults={
                    'registration_number': student_data['reg'],
                    'programme': dswe,
                    'academic_period': period,
                    'year_of_study': 1,
                    'is_active': True,
                }
            )
        
        # Create lecturers
        lecturers_data = [
            {'name': 'Wandeka Joyce', 'staff_no': 'UICT/STAFF/20251', 'username': 'wandeka_joyce', 'password': 'wandeka123'},
            {'name': 'Kampororo Ezra', 'staff_no': 'UICT/STAFF/20252', 'username': 'kampororo_ezra', 'password': 'kampororo123'},
            {'name': 'Sewemuwe SIM', 'staff_no': 'UICT/STAFF/20253', 'username': 'sewemuwe_sim', 'password': 'sewemuwe123'},
        ]
        
        for lecturer_data in lecturers_data:
            name_parts = lecturer_data['name'].split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            user, created = User.objects.get_or_create(
                username=lecturer_data['username'],
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': 'lecturer',
                    'is_active': True,
                    'is_verified': True,
                }
            )
            if created:
                user.set_password(lecturer_data['password'])
                user.save()
                self.stdout.write(f'✓ Created lecturer: {lecturer_data["name"]}')
            
            lecturer, created = Lecturer.objects.get_or_create(
                user=user,
                defaults={
                    'staff_number': lecturer_data['staff_no'],
                    'academic_period': period,
                    'is_active': True,
                }
            )
        
        # Create course units
        course_units_data = [
            {'code': 'UIUX101', 'name': 'Foundation of UI/UX Design', 'lecturer': 'wandeka_joyce'},
            {'code': 'ST101', 'name': 'Software Testing', 'lecturer': 'kampororo_ezra'},
            {'code': 'PM101', 'name': 'ICT Project Management', 'lecturer': 'sewemuwe_sim'},
        ]
        
        for course_data in course_units_data:
            lecturer = User.objects.get(username=course_data['lecturer'])
            course, created = CourseUnit.objects.get_or_create(
                code=course_data['code'],
                defaults={
                    'name': course_data['name'],
                    'programme': dswe,
                    'academic_period': period,
                    'lecturer': lecturer,
                    'year_of_study': 1,
                    'is_active': True,
                }
            )
            self.stdout.write(f'✓ Course unit: {course}')
        
        # Create sample lectures
        today = datetime.date.today()
        for lecturer_data in lecturers_data:
            lecturer = User.objects.get(username=lecturer_data['username'])
            courses = CourseUnit.objects.filter(lecturer=lecturer)
            for course in courses:
                Lecture.objects.get_or_create(
                    course_unit=course,
                    lecturer=lecturer,
                    academic_period=period,
                    programme=dswe,
                    title=f"{course.name} - Lecture 1",
                    lecture_type='PHYSICAL',
                    status='scheduled',
                    scheduled_date=today,
                    start_time=datetime.time(9, 0),
                    end_time=datetime.time(11, 0),
                    location='Room 101',
                )
                Lecture.objects.get_or_create(
                    course_unit=course,
                    lecturer=lecturer,
                    academic_period=period,
                    programme=dswe,
                    title=f"{course.name} - Lecture 2",
                    lecture_type='ONLINE',
                    status='scheduled',
                    scheduled_date=today + datetime.timedelta(days=2),
                    start_time=datetime.time(14, 0),
                    end_time=datetime.time(16, 0),
                    location='Online',
                )
        self.stdout.write('✓ Created sample lectures')
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ Demo data seeded successfully!'))
        self.stdout.write('=' * 60)
        self.stdout.write('\n📋 DEMO CREDENTIALS:')
        self.stdout.write('─' * 40)
        self.stdout.write('👑 ADMIN:')
        self.stdout.write('   Username: khuzaifah')
        self.stdout.write('   Password: kamcoder812')
        self.stdout.write('\n👨‍🎓 STUDENTS (Username = Registration number, Password = Full name):')
        for student in students_data:
            self.stdout.write(f'   {student["reg"]} / {student["name"]}')
        self.stdout.write('\n👨‍🏫 LECTURERS:')
        for lecturer in lecturers_data:
            self.stdout.write(f'   {lecturer["username"]} / {lecturer["password"]}')
        self.stdout.write('\n' + '=' * 60)