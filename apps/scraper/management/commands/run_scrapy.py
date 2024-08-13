from django.core.management.base import BaseCommand
from scraper.tasks import run_spider


class Command(BaseCommand):
    help = "Runs celery tasks"

    def handle(self, *args, **options):
        run_spider.delay()
