from django.urls import path
from . import views
from . import views_admin

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    path('admin/manage-students/', views_admin.admin_manage_students, name='admin_manage_students'),
    path('admin/manage-lecturers/', views_admin.admin_manage_lecturers, name='admin_manage_lecturers'),
    path('admin/manage-course-units/', views_admin.admin_manage_course_units, name='admin_manage_course_units'),
    
    path('api/admin/add-students-bulk/', views_admin.admin_add_students_bulk, name='admin_add_students_bulk'),
    path('api/admin/add-lecturers-bulk/', views_admin.admin_add_lecturers_bulk, name='admin_add_lecturers_bulk'),
    path('api/admin/add-course-units-bulk/', views_admin.admin_add_course_units_bulk, name='admin_add_course_units_bulk'),
    path('api/admin/get-students/', views_admin.admin_get_students_list, name='admin_get_students'),
    path('api/admin/get-lecturers/', views_admin.admin_get_lecturers_list, name='admin_get_lecturers'),
    path('api/admin/get-course-units/', views_admin.admin_get_course_units_list, name='admin_get_course_units'),
    path('api/admin/get-programmes/', views_admin.admin_get_programmes_list, name='admin_get_programmes'),
]