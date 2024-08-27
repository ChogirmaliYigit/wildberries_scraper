import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "scrape_wildberries_products": {
        "task": "scrape_products",
        "schedule": 10,  # settings.SCRAPE_PRODUCTS_SECONDS,
    },
    "scrape_wildberries_comments": {
        "task": "scrape_comments",
        "schedule": 20,  # settings.SCRAPE_COMMENTS_SECONDS
    },
}
app.conf.timezone = "Asia/Tashkent"


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


@app.task(name="scrape_products", bind=True)
def scrape_products(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_products()
    wildberries.get_all_product_variant_images()


@app.task(name="scrape_comments", bind=True)
def scrape_comments(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_product_comments()
