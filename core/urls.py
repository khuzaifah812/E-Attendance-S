from django.urls import path
from . import views

urlpatterns = [
    # ==================== AUTHENTICATION ====================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # ==================== USER PROFILE ====================
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile_view, name='update_profile'),
    
    # ==================== NOTIFICATIONS ====================
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/clear/', views.clear_notifications, name='clear_notifications'),
    
    # ==================== STUDENT VIEWS ====================
    path('attendance-history/', views.attendance_history_view, name='attendance_history'),
    path('timetable/', views.timetable_view, name='timetable'),
    path('course-units/', views.course_units_view, name='course_units'),
    
    # ==================== HEALTH CHECK ====================
    path('health/', views.health_check, name='health_check'),
    
    # ==================== ADMIN MANAGEMENT - STUDENTS ====================
    path('admin/manage-students/', views.admin_manage_students, name='admin_manage_students'),
    path('api/admin/add-students-bulk/', views.admin_add_students_bulk, name='admin_add_students_bulk'),
    path('api/admin/get-students/', views.admin_get_students_list, name='admin_get_students'),
    path('api/admin/delete-student/<int:student_id>/', views.admin_delete_student, name='admin_delete_student'),
    path('api/admin/activate-student/<int:student_id>/', views.admin_activate_student, name='admin_activate_student'),
    path('api/admin/reset-student-password/<int:student_id>/', views.admin_reset_student_password, name='admin_reset_student_password'),
    
    # ==================== ADMIN MANAGEMENT - LECTURERS ====================
    path('admin/manage-lecturers/', views.admin_manage_lecturers, name='admin_manage_lecturers'),
    path('api/admin/add-lecturers-bulk/', views.admin_add_lecturers_bulk, name='admin_add_lecturers_bulk'),
    path('api/admin/get-lecturers/', views.admin_get_lecturers_list, name='admin_get_lecturers'),
    path('api/admin/delete-lecturer/<int:lecturer_id>/', views.admin_delete_lecturer, name='admin_delete_lecturer'),
    path('api/admin/activate-lecturer/<int:lecturer_id>/', views.admin_activate_lecturer, name='admin_activate_lecturer'),
    path('api/admin/reset-lecturer-password/<int:lecturer_id>/', views.admin_reset_lecturer_password, name='admin_reset_lecturer_password'),
    
    # ==================== ADMIN MANAGEMENT - COURSE UNITS ====================
    path('admin/manage-course-units/', views.admin_manage_course_units, name='admin_manage_course_units'),
    path('api/admin/add-course-units-bulk/', views.admin_add_course_units_bulk, name='admin_add_course_units_bulk'),
    path('api/admin/get-course-units/', views.admin_get_course_units_list, name='admin_get_course_units'),
    path('api/admin/delete-course-unit/<int:course_id>/', views.admin_delete_course_unit, name='admin_delete_course_unit'),
    path('api/admin/activate-course-unit/<int:course_id>/', views.admin_activate_course_unit, name='admin_activate_course_unit'),
    
    # ==================== ADMIN MANAGEMENT - PROGRAMMES ====================
    path('admin/manage-programmes/', views.admin_manage_programmes, name='admin_manage_programmes'),
    path('api/admin/add-programme/', views.admin_add_programme, name='admin_add_programme'),
    path('api/admin/get-programmes/', views.admin_get_programmes_list, name='admin_get_programmes'),
    path('api/admin/update-programme/<int:programme_id>/', views.admin_update_programme, name='admin_update_programme'),
    path('api/admin/delete-programme/<int:programme_id>/', views.admin_delete_programme, name='admin_delete_programme'),
    
    # ==================== ADMIN MANAGEMENT - LECTURES ====================
    path('admin/manage-lectures/', views.admin_manage_lectures, name='admin_manage_lectures'),
    path('api/admin/add-lecture/', views.admin_add_lecture, name='admin_add_lecture'),
    path('api/admin/add-lectures-bulk/', views.admin_add_lectures_bulk, name='admin_add_lectures_bulk'),
    path('api/admin/update-lecture/<int:lecture_id>/', views.admin_update_lecture, name='admin_update_lecture'),
    path('api/admin/delete-lecture/<int:lecture_id>/', views.admin_delete_lecture, name='admin_delete_lecture'),
    path('api/admin/get-lecture/<int:lecture_id>/', views.admin_get_lecture_detail, name='admin_get_lecture_detail'),
    path('api/admin/get-lectures/', views.admin_get_lectures_list, name='admin_get_lectures'),
]