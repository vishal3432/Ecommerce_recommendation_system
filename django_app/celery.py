import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_app.settings')

app = Celery('django_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic Tasks Configuration
app.conf.beat_schedule = {
    # Train ML model daily at 2 AM
    'train-ml-model-daily': {
        'task': 'ecommerce.tasks.train_ml_model',
        'schedule': crontab(hour=2, minute=0),
    },
    # Generate recommendations for active users every 6 hours
    'batch-recommendations-6h': {
        'task': 'ecommerce.tasks.batch_generate_recommendations',
        'schedule': crontab(minute=0, hour='*/6'),
        'kwargs': {'limit': 1000}
    },
    # Clean old tasks every week
    'clean-old-tasks-weekly': {
        'task': 'ecommerce.tasks.clean_old_tasks',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
    },
}

# Celery Configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minute hard limit
    task_soft_time_limit=25 * 60,  # 25 minute soft limit
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
