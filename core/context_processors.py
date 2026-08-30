from academics.models import AcademicPeriod

def current_academic_period(request):
    return {
        'current_period': AcademicPeriod.objects.filter(is_current=True).first()
    }