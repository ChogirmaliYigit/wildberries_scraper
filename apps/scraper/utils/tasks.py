from django_apscheduler import util
from django_apscheduler.models import DjangoJobExecution
from scraper.utils import wildberries


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """
    This job deletes APScheduler job execution entries older than `max_age` from the database.
    It helps to prevent the database from filling up with old historical records that are no
    longer useful.

    :param max_age: The maximum length of time to retain historical job execution records.
                                    Defaults to 7 days.
    """
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


def scrape_top_level_categories():
    wildberries.get_top_level_categories_list()


def scrape_sub_categories_by_parent():
    wildberries.get_sub_categories_by_parent()


def scrape_products_list_by_category():
    wildberries.get_products_list_by_category()
