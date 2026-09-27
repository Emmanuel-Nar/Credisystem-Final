release: python manage.py migrate --noinput
web: gunicorn credisystem.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile - --error-logfile -
