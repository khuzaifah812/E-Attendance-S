#!/bin/sh
set -e

echo ">>> RUNNING MIGRATIONS - Creating tables if not exist..."
python manage.py migrate --noinput

echo ">>> MIGRATIONS DONE"
echo ">>> Starting Gunicorn..."

exec "$@"