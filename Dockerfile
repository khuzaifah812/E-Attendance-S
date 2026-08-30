FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/logs /app/media /app/staticfiles
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y \
    gcc \
    libmariadb-dev \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p logs media staticfiles
RUN python manage.py collectstatic --noinput || true
CMD python manage.py migrate --no-input; DJANGO_SUPERUSER_USERNAME=khuzaifah DJANGO_SUPERUSER_EMAIL=khuzaifah@uict.ac.ug DJANGO_SUPERUSER_PASSWORD=kamcoder812 python manage.py createsuperuser --no-input || true; python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u=U.objects.get(username='khuzaifah'); u.is_staff=True; u.is_superuser=True; setattr(u,'role','admin') if hasattr(u,'role') else None; setattr(u,'user_type','admin') if hasattr(u,'user_type') else None; u.save(); print('FIXED ROLE:', getattr(u,'role','no-role-field'))" || true; gunicorn config.wsgi:application --bind 0.0.0.0:8000