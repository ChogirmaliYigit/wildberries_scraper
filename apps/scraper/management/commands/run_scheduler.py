from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from scraper.utils import tasks


class Command(BaseCommand):
    help = "Runs apscheduler"

    def add_arguments(self, parser):
        # Define an argument 'scraper_type'
        parser.add_argument(
            "scraper_type",
            choices=["category", "sub_category", "product", "all"],
            help="Specify the type of scraper to run. Choices are 'category', 'sub_category', 'product' or 'all'.",
        )

    def handle(self, *args, **options):
        scraper_type = options["scraper_type"]

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        if scraper_type == "all":
            scheduler.add_job(
                tasks.scrape_top_level_categories, trigger="interval", seconds=5
            )
            scheduler.add_job(
                tasks.scrape_sub_categories_by_parent, trigger="interval", seconds=5
            )
            scheduler.add_job(
                tasks.scrape_products_list_by_category, trigger="interval", seconds=5
            )
        elif scraper_type == "category":
            scheduler.add_job(
                tasks.scrape_top_level_categories, trigger="interval", seconds=5
            )
        elif scraper_type == "sub_category":
            scheduler.add_job(
                tasks.scrape_sub_categories_by_parent, trigger="interval", seconds=5
            )
        elif scraper_type == "product":
            scheduler.add_job(
                tasks.scrape_products_list_by_category, trigger="interval", seconds=5
            )

        scheduler.add_job(
            tasks.delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="mon", hour="00", minute="00"
            ),  # Midnight on Monday, before the start of the next work week.
            max_instances=1,
            replace_existing=True,
        )

        try:
            scheduler.start()
        except KeyboardInterrupt:
            scheduler.shutdown()
