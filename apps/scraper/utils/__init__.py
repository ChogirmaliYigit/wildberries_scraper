from django.conf import settings

from .wildberries_client import WildberriesClient

wildberries = WildberriesClient(settings.WILDBERRIES_BASE_SCRAPE_URL)
