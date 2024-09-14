import os

from django.conf import settings

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "scrape_wildberries_categories": {
        "task": "scrape_categories",
        "schedule": settings.SCRAPE_CATEGORIES_SECONDS,
    },
    "scrape_wildberries_products": {
        "task": "scrape_products",
        "schedule": settings.SCRAPE_PRODUCTS_SECONDS,
    },
    "scrape_wildberries_comments": {
        "task": "scrape_comments",
        "schedule": settings.SCRAPE_COMMENTS_SECONDS,
    },
    "scrape_wildberries_product_images": {
        "task": "scrape_product_images",
        "schedule": 10,
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


@app.task(name="scrape_comments", bind=True)
def scrape_comments(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_product_comments()


@app.task(name="scrape_product_images", bind=True)
def scrape_product_images(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_all_product_variant_images()


@app.task(name="scrape_categories", bind=True)
def scrape_categories(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_categories()
