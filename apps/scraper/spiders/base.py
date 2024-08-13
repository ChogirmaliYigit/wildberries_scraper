import scrapy


class BaseSpider(scrapy.Spider):
    allowed_domains = ["wildberries.ru"]
