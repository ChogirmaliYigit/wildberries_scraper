from django.conf import settings
from scraper.spiders import BaseSpider


class CommentSpider(BaseSpider):
    name = "comment_spider"

    start_urls = [
        settings.WILDBERRIES_BASE_SCRAPE_URL,
    ]

    def parse(self, response):
        pass
