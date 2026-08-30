from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import JsonResponse
from core import views as core_views  # <-- add this

def health_check(request):
    return JsonResponse({'status': 'ok', 'message': 'UICT-ESAS is running'})

urlpatterns = [
    # YOUR CUSTOM ADMIN PAGES - MUST BE FIRST
    path('admin/manage-lecturers/', core_views.manage_lecturers, name='manage-lecturers'),
    path('admin/manage-students/', core_views.manage_students, name='manage-students'),
    path('admin/manage-course-units/', core_views.manage_course_units, name='manage-course-units'),
    path('admin/dashboard/', core_views.admin_dashboard, name='admin-dashboard'),

    # Django default
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    path('health/', health_check, name='health_check'),
    path('api/', include('core.api_urls')),
    path('', include('core.urls')),
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)