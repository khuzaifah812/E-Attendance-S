from django.urls import path, include
from rest_framework.routers import DefaultRouter
from attendance.api_views import AttendanceViewSet

router = DefaultRouter()
router.register(r'attendance', AttendanceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]