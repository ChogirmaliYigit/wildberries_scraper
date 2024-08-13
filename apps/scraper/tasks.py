from celery import shared_task
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from apps.scraper.spiders import CategorySpider, CommentSpider, ProductSpider


@shared_task
def scrape_categories():
    process = CrawlerProcess(get_project_settings())
    process.crawl(CategorySpider)
    process.start()


@shared_task
def scrape_products():
    process = CrawlerProcess(get_project_settings())
    process.crawl(ProductSpider)
    process.start()


@shared_task
def scrape_comments():
    process = CrawlerProcess(get_project_settings())
    process.crawl(CommentSpider)
    process.start()


# Schedule scraping tasks
def setup_periodic_tasks(sender, **kwargs):
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=5, period=IntervalSchedule.SECONDS
    )
    PeriodicTask.objects.create(
        interval=schedule,
        name="Scrape Wildberries Categories",
        task="scraper.tasks.scrape_categories",
    )

    # product_schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.HOURS)
    # PeriodicTask.objects.create(interval=product_schedule, name='Scrape Wildberries Products', task='scraper.tasks.scrape_products')
    #
    # comment_schedule, _ = IntervalSchedule.objects.get_or_create(every=30, period=IntervalSchedule.MINUTES)
    # PeriodicTask.objects.create(interval=comment_schedule, name='Scrape Wildberries Comments', task='scraper.tasks.scrape_comments')
