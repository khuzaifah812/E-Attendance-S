#!/bin/sh
echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT