from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from academics.models import AcademicYear, Semester, AcademicPeriod
from programmes.models import Programme
from students.models import Student
from lecturers.models import Lecturer
from courses.models import CourseUnit
from lectures.models import Lecture
from .models import Attendance
import datetime

User = get_user_model()

class AttendanceSystemTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            year='2025/2026',
            start_date=datetime.date(2025, 8, 1),
            end_date=datetime.date(2026, 7, 31),
            is_active=True
        )
        
        self.semester = Semester.objects.create(
            academic_year=self.academic_year,
            name='1',
            start_date=datetime.date(2025, 8, 15),
            end_date=datetime.date(2025, 12, 15),
            is_active=True
        )
        
        self.period = AcademicPeriod.objects.create(
            academic_year=self.academic_year,
            semester=self.semester,
            is_current=True
        )
        
        self.programme = Programme.objects.create(
            code='DSWE',
            name='Diploma in Software Engineering',
            duration=4,
            session='DAY',
            is_active=True
        )
        
        self.student_user = User.objects.create_user(
            username='UICT/2025/DSWE/DAY/2246',
            password='AINE MBABAZI KHUZAIFAH',
            first_name='AINE MBABAZI',
            last_name='KHUZAIFAH',
            role='student'
        )
        
        self.student = Student.objects.create(
            user=self.student_user,
            registration_number='UICT/2025/DSWE/DAY/2246',
            programme=self.programme,
            academic_period=self.period,
            year_of_study=1,
            is_active=True
        )
        
        self.lecturer_user = User.objects.create_user(
            username='wandeka_joyce',
            password='wandeka123',
            first_name='Wandeka',
            last_name='Joyce',
            role='lecturer',
            is_verified=True
        )
        
        self.lecturer = Lecturer.objects.create(
            user=self.lecturer_user,
            staff_number='UICT/STAFF/20251',
            academic_period=self.period,
            is_active=True
        )
        
        self.course_unit = CourseUnit.objects.create(
            code='UIUX101',
            name='Foundation of UI/UX Design',
            programme=self.programme,
            academic_period=self.period,
            lecturer=self.lecturer_user,
            year_of_study=1,
            is_active=True
        )
    
    def test_student_creation(self):
        self.assertEqual(self.student.registration_number, 'UICT/2025/DSWE/DAY/2246')
    
    def test_lecture_creation(self):
        lecture = Lecture.objects.create(
            course_unit=self.course_unit,
            lecturer=self.lecturer_user,
            academic_period=self.period,
            programme=self.programme,
            title='Introduction to UI/UX',
            lecture_type='PHYSICAL',
            status='scheduled',
            scheduled_date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0)
        )
        self.assertEqual(lecture.title, 'Introduction to UI/UX')
    
    def test_attendance_creation(self):
        lecture = Lecture.objects.create(
            course_unit=self.course_unit,
            lecturer=self.lecturer_user,
            academic_period=self.period,
            programme=self.programme,
            title='Introduction to UI/UX',
            lecture_type='PHYSICAL',
            status='active',
            scheduled_date=datetime.date.today(),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            actual_start=timezone.now(),
            verification_code='UICT-ABC123'
        )
        
        attendance = Attendance.objects.create(
            student=self.student,
            lecture=lecture,
            academic_period=self.period,
            status='present',
            ip_address='127.0.0.1',
            verification_code_used='UICT-ABC123',
            verification_result='success'
        )
        
        self.assertEqual(attendance.student, self.student)
        self.assertEqual(attendance.status, 'present')