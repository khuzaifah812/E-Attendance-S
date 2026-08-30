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


CMD python manage.py migrate admin zero --fake || true; python manage.py migrate --no-input || python manage.py migrate --fake-initial --no-input; python manage.py migrate --no-input; gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2D sh -c "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:10000"