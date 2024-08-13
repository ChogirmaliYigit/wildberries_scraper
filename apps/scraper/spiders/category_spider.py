import logging

from django.conf import settings
from scraper.spiders import BaseSpider

logger = logging.getLogger(__name__)


class CategorySpider(BaseSpider):
    name = "category_spider"

    start_urls = [
        settings.WILDBERRIES_BASE_SCRAPE_URL,
    ]

    def parse(self, response):
        logger.info("CategorySpider.parse() run")
        # catalog_div = response.css('div.menu-burger__main.j-menu-burger-main')
        # catalog_ul = catalog_div.css("ul.menu-burger__main-list")
        # catalog_items = catalog_ul.css("li.menu-burger__main-list-item.j-menu-main-item")
        #
        # categories_objects = []
        # for item in catalog_items:
        #     title = item.css("span::text").get() or item.xpath("text()").get()
        #     source_id = item.attrib.get("data-menu-id")
        #     if title and source_id:
        #         categories_objects.append(
        #             Category(
        #                 title=title.strip(),
        #                 source_id=int(source_id),
        #             )
        #         )
        #
        # if categories_objects:
        #     Category.objects.bulk_create(categories_objects, ignore_conflicts=True)
