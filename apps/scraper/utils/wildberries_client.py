import json
import random
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse
from django.db import IntegrityError, transaction
from django.db.models import Count
from fake_useragent import UserAgent
from requests_html import HTMLSession
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    FileTypeChoices,
    Product,
)


class WildberriesClient:
    def __init__(self):
        self.ua = UserAgent()

    def get_headers(self, url):
        return {
            "User-Agent": "python-requests/2.32.3",
            "Accept-Language": "en,uz;q=0.9,ru;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept": "application/json; charset=utf-8",
            "Upgrade-Insecure-Requests": "1",
            "Host": "catalog.wb.ru",
        }

    def send_request(self, url):
        data = {}
        try:
            session = HTMLSession()
            response = session.get(url, headers=self.get_headers(url), timeout=10)
            if response.status_code == 200:
                try:
                    data = response.json()
                except requests.exceptions.JSONDecodeError as exc:
                    data = {}
        except requests.exceptions.RequestException as exc:
            pass
        return data

    def get_soup(
        self, url: str = None, image: bool = False
    ) -> BeautifulSoup | None | str:
        """Returns a BeautifulSoup object of the requested URL's HTML content."""
        try:
            session = HTMLSession()
            response = session.get(url, headers=self.get_headers(url))

            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type and image:
                return "image"
            if response.status_code != 200:
                return None
        except requests.exceptions.ConnectionError:
            return None
        return BeautifulSoup(response.content, "html.parser")

    def check_image(self, image_url: str) -> bool:
        """Checks if an image exists at the given URL."""
        soup = self.get_soup(image_url, image=True)
        if isinstance(soup, str) and soup == "image":
            return True
        elif isinstance(soup, BeautifulSoup):
            title = soup.find("title")
            if title and hasattr(title, "text") and title.text != "404 Not Found":
                return True
        return False

    def get_categories(self):
        """Fetches and saves categories and subcategories from Wildberries."""

        # Step 1: Retrieve top-level categories from the database
        top_categories = Category.objects.all().order_by("?")

        # Step 2: Fetch Wildberries categories data
        with open("apps/scraper/fixtures/categories.json", encoding="utf-8") as file:
            wildberries_categories = json.load(file)

        # Step 3: Iterate over top-level categories from the database
        for top_category in top_categories:
            # Find the corresponding Wildberries top-level category by source_id
            matching_wb_category = next(
                (
                    wb_cat
                    for wb_cat in wildberries_categories
                    if wb_cat["id"] == top_category.source_id
                ),
                None,
            )

            if not matching_wb_category:
                continue

            # Step 4: Get subcategories (childs) for the top-level category
            subcategories = matching_wb_category.get("childs", [])

            # Step 5: Save each subcategory to the database
            for subcategory in subcategories:
                subcategory_name = subcategory["name"]
                existing_subcategory = Category.objects.filter(
                    title=subcategory_name, parent=top_category
                ).first()

                # Handle duplicate subcategory names by appending the top-level category name
                if existing_subcategory:
                    subcategory_name = f"{subcategory_name} {top_category.title}"
                    existing_subcategory.title = subcategory_name
                    try:
                        existing_subcategory.save(update_fields=["title"])
                    except IntegrityError:
                        pass
                    continue

                try:
                    Category.objects.create(
                        source_id=subcategory["id"],
                        title=subcategory_name,
                        slug_name=subcategory.get("url", ""),
                        shard=subcategory.get("shard", ""),
                        parent=top_category,
                    )
                except IntegrityError:
                    pass

    def get_categories_with_few_products(self, initial_limit=10, max_limit=100):  # noqa
        limit = initial_limit

        # Loop until we find categories or reach the max limit
        while limit <= max_limit:
            # Annotate each category with a count of related products
            categories = (
                Category.objects.annotate(product_count=Count("products"))
                .filter(product_count__lt=limit)
                .order_by("?")  # Random order
            )

            # If we found matching categories, return them
            if categories.exists():
                return categories

            # Increase the limit and try again
            limit += 10

        # Return empty if no matching categories were found even after reaching max limit
        return Category.objects.none()

    def update_products(self):
        currency = "rub"

        for product in Product.objects.filter(source_id__isnull=True):
            category = product.category
            if not category:
                continue

            # Construct the URL for the API request
            url = (
                f"http://catalog.wb.ru/catalog/{category.shard}/v2/catalog"
                f"?ab_testing=false&appType=1&cat={category.source_id}&curr={currency}&dest=491&sort=popular&spp=30"
                f"&uclusters=0"
            )
            # Send request to get product data
            data = self.send_request(url)

            # Extract a product list from the API response
            products_data = data.get("data", {}).get("products", [])

            # Search for the product title in the products_data
            for item in products_data:
                product_title = item.get("name", "").lower()
                target_title = product.title.lower()

                # Check if the target title is found in the product title
                if target_title in product_title:
                    product.source_id = item.get("id")
                    product.save()
                    break  # Exit the loop once a match is found

    def get_products(self, categories=None):
        """Fetches and saves products and their variants."""
        currency = "rub"
        if not categories:
            categories = self.get_categories_with_few_products(
                max_limit=Product.objects.count()
            )
        existing_source_ids = set(Product.objects.values_list("source_id", flat=True))

        for category in categories:
            url = (
                f"http://catalog.wb.ru/catalog/{category.shard}/v2/catalog"
                f"?ab_testing=false&appType=1&cat={category.source_id}&curr={currency}&dest=491&sort=popular&spp=30"
                f"&uclusters=0"
            )
            data = self.send_request(url)

            if not data:
                data = self.send_request(
                    f"https://catalog.wb.ru/catalog/{category.shard}/v2/catalog?ab_pers_testid=newlogscore"
                    f"&ab_rec_testid=newlogscore&ab_testid=newlogscore&appType=1&cat={category.source_id}&curr={currency}&dest=491&sort"
                    "=popular&spp=30&uclusters=0"
                )

            products_data = data.get("data", {}).get("products", [])
            if not products_data:
                sub_categories = category.sub_categories.all()
                if sub_categories:
                    self.get_products(sub_categories)
            random.shuffle(products_data)
            roots = {}
            for product in products_data:
                roots.setdefault(product["root"], []).append(product)

            for root, products in roots.items():
                self.save_products_and_variants(
                    category, root, products, existing_source_ids
                )

    @transaction.atomic
    def save_products_and_variants(self, category, root, products, existing_source_ids):
        """Saves products and their variants"""
        for product in products:
            source_id = product["id"]
            if source_id in existing_source_ids:
                continue

            data = {
                "title": product.get("name"),
                "source_id": source_id,
                "defaults": {
                    "category": category,
                    "root": int(root),
                },
            }

            try:
                Product.objects.get_or_create(**data)
            except Exception:
                pass

    def get_category_by_slug_name(self, slug_name):
        wildberries_categories = self.send_request(
            "https://static-basket-01.wb.ru/vol0/data/main-menu-ru-ru-v2.json"
        )

        # Iterate through the categories to find a match
        for category in wildberries_categories:
            # Check if the slug_name is present in the 'url' field
            if slug_name in category["url"]:
                return category

            # If the category has children, search in them as well
            if "childs" in category:
                for subcategory in category["childs"]:
                    if slug_name in subcategory["url"]:
                        return subcategory

        # If no category is found
        return None

    def get_product_category(self, source_id) -> Category | None:
        variant_detail_soup = self.get_soup(
            f"https://www.wildberries.ru/catalog/{source_id}/detail.aspx"
        )
        if not variant_detail_soup:
            return None

        product_page = variant_detail_soup.find("div", {"class": "product-page"})
        if not product_page:
            return None
        breadcrumb_ul = product_page.find_next("ul", {"class": "breadcrumbs__list"})
        if not breadcrumb_ul:
            return None
        breadcrumbs = breadcrumb_ul.find_all("li", {"class": "breadcrumbs__item"})
        if not breadcrumbs:
            return None
        anchor_tag = breadcrumbs[1].find_next("a", {"class": "breadcrumbs__link"})
        if not anchor_tag:
            return None
        slug_name = anchor_tag["href"]
        category = Category.objects.filter(slug_name=slug_name).last()
        if not category:
            category_data = self.get_category_by_slug_name(slug_name)
            if not isinstance(category_data, dict):
                return None
            category = Category.objects.create(
                slug_name=category_data.get("url"),
                title=category_data.get("name"),
                shard=category_data.get("shard"),
                parent=Category.objects.filter(
                    parent__source_id=category_data.get("parent")
                ).first(),
            )
        return category

    @transaction.atomic
    def get_product_by_source_id(self, source_id: int) -> Product | None:
        """Scrapes a product and its variants by the given source_id."""
        currency = "rub"
        url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr={currency}&dest=491&spp=30&ab_testing=false&nm={source_id}"
        product_data = self.send_request(url)
        if not product_data:
            return None

        if not product_data.get("data"):
            return None

        product_info = product_data["data"]["products"][0]

        _data = {
            "root": product_info["root"],
            "defaults": {
                "title": product_info["name"],
                "category": self.get_product_category(source_id),
                "source_id": source_id,
            },
        }

        try:
            product_object, _ = Product.objects.get_or_create(**_data)
        except Exception:
            product_object = None

        return product_object

    def get_product_comments(self):
        """Fetches and saves product comments."""
        products = Product.objects.values("root", "id").order_by("?")
        roots = set()

        for product in products:
            root = product["root"]
            if root in roots:
                continue
            roots.add(root)

            url = f"https://feedbacks2.wb.ru/feedbacks/v1/{root}"
            data = self.send_request(url)

            feedbacks = data.get("feedbacks", [])
            if not feedbacks:
                continue

            for comment in feedbacks:
                self.save_comment(comment, product["id"])

    @transaction.atomic
    def save_comment(self, comment, product_id):
        """Saves a comment and its images."""
        created_date = comment.get("createdDate")
        try:
            published_date = (
                parse(created_date, yearfirst=True) if created_date else None
            )
        except ParserError:
            published_date = None

        if (
            not published_date
            or (datetime.now(timezone.utc) - timedelta(weeks=2)) > published_date
        ):
            return

        rating = comment.get("productValuation", 0)
        if rating != 5:
            return

        if comment.get("text"):
            comment_object, _ = Comment.objects.get_or_create(
                product_id=product_id,
                content=comment.get("text"),
                defaults={
                    "rating": rating,
                    "status": CommentStatuses.ACCEPTED,
                    "wb_user": comment.get("wbUserDetails", {}).get("name", ""),
                    "source_date": published_date,
                },
            )

            images_saved = self.save_comment_images(
                comment_object, comment.get("photo", [])
            )
            video_saved = self.save_comment_videos(
                comment_object, comment.get("video", None)
            )

            if not images_saved and not video_saved:
                comment_object.delete()

    def save_comment_images(self, comment_object, photo_ids):
        """Saves images associated with a comment."""
        image_objects = []

        for photo_id in photo_ids:
            photo_id = str(photo_id)
            link = None
            for basket_id in range(1, 11):
                img_url = f"https://feedback0{basket_id}.wbbasket.ru/vol{photo_id[:4]}/part{photo_id[:6]}/{photo_id}/photos/ms.webp"
                if self.check_image(img_url):
                    link = img_url
                    break

            if link:
                image_objects.append(
                    CommentFiles(
                        comment=comment_object,
                        file_link=link,
                        file_type=FileTypeChoices.IMAGE,
                    )
                )
        if image_objects:
            CommentFiles.objects.bulk_create(image_objects, ignore_conflicts=True)
            return True
        return False

    def save_comment_videos(self, comment_object, video):
        """Saves videos associated with a comment."""
        if isinstance(video, dict):
            basket_id, uuid = video["id"].split("/")
            link = "https://videofeedback0{}.wbbasket.ru/{}/index.m3u8".format(
                basket_id, uuid
            )
            if link:
                comment = CommentFiles.objects.filter(comment=comment_object)
                if not comment:
                    CommentFiles.objects.get_or_create(
                        comment=comment_object,
                        file_type=FileTypeChoices.VIDEO,
                        defaults={
                            "file_link": link,
                        },
                    )
                    return True
        return False
