from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ScraperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scraper"
    verbose_name = _("Data")

    def ready(self):
        import scraper.signals  # noqa
