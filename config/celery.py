from celery import Celery

app = Celery("wildberries_scraper")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
