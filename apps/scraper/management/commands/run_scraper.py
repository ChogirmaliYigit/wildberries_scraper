from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from scraper.utils import tasks


class Command(BaseCommand):
    help = "Runs scrapers by type"

    def add_arguments(self, parser):
        # Define an argument 'scraper_type'
        parser.add_argument(
            "scraper_type",
            choices=["category", "product", "comment", "all"],
            help="Specify the type of scraper to run. Choices are 'category', 'product', 'comment' or 'all'.",
        )
        parser.add_argument(
            "interval",
            type=int,
            help="Specify the interval in seconds for running the scraper jobs.",
        )

    def handle(self, *args, **options):
        scraper_type = options["scraper_type"]
        interval = options["interval"]

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        if scraper_type == "all":
            scheduler.add_job(
                tasks.scrape_categories, trigger="interval", seconds=interval
            )
            scheduler.add_job(
                tasks.scrape_products, trigger="interval", seconds=interval
            )
            scheduler.add_job(
                tasks.scrape_product_comments, trigger="interval", seconds=interval
            )
        elif scraper_type == "category":
            scheduler.add_job(
                tasks.scrape_categories, trigger="interval", seconds=interval
            )
        elif scraper_type == "product":
            scheduler.add_job(
                tasks.scrape_products, trigger="interval", seconds=interval
            )
        elif scraper_type == "comment":
            scheduler.add_job(
                tasks.scrape_product_comments, trigger="interval", seconds=interval
            )

        scheduler.add_job(
            tasks.delete_old_job_executions,
            trigger="interval",
            days=1,
            max_instances=1,
            replace_existing=True,
        )

        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown()
