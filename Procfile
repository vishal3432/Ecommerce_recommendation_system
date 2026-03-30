web: gunicorn django_app.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A django_app worker -l info
beat: celery -A django_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
