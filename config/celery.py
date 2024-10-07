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
    "update_wildberries_products": {
        "task": "update_products",
        "schedule": 60,
    },
    "caching_products_and_comments": {
        "task": "schedule_caching_for_products_and_comments",
        "schedule": settings.CACHE_PRODUCTS_AND_COMMENTS_SECONDS,
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


@app.task(name="scrape_categories", bind=True)
def scrape_categories(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.get_categories()


@app.task(name="update_products", bind=True)
def update_products(*args, **kwargs):
    from scraper.utils import wildberries

    wildberries.update_products()


@app.task(name="schedule_caching_for_products_and_comments", bind=True)
def schedule_caching_for_products_and_comments(*args, **kwargs):
    from django.core.cache import cache
    from scraper.utils.queryset import cache_feedbacks_task, get_all_products

    products = get_all_products()
    cache.set("all_products", products, timeout=settings.CACHE_DEFAULT_TIMEOUT)

    cache_feedbacks_task.delay([product.id for product in products[:100]])

    return f"{len(products)} products cached"
