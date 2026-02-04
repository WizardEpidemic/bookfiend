# Configures the Celery application used for BookFiend background scan processing.

from celery import Celery

from app.config import settings


celery_app = Celery(
    "bookfiend",
    broker=settings.redis_url,
    include=["app.tasks.process_scan"],
)

celery_app.conf.update(
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
)