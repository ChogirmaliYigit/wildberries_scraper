from django_apscheduler import util
from django_apscheduler.models import DjangoJobExecution
from scraper.utils import wildberries


@util.close_old_connections
def delete_old_job_executions(max_age=3_600):
    """
    This job deletes APScheduler job execution entries older than `max_age` from the database.
    It helps to prevent the database from filling up with old historical records that are no
    longer useful.

    :param max_age: The maximum length of time to retain historical job execution records.
                                    Defaults to an hour.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def scrape_categories():
    wildberries.get_categories()


def scrape_products():
    wildberries.get_products()


def scrape_product_comments():
    wildberries.get_product_comments()
