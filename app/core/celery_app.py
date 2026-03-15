from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "sistemahotel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Task modules are registered here as they are created in later plans.
    include=[],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
