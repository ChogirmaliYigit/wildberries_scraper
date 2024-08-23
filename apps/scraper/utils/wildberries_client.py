import json
import random
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse
from django.conf import settings
from django.db import transaction
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    Product,
    ProductVariant,
    ProductVariantImage,
)

from .driver import WebDriver


class WildberriesClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.driver = WebDriver

    def get_soup(self, url: str = None, scroll_bottom: bool = False) -> BeautifulSoup:
        """Returns a BeautifulSoup object of the requested URL's HTML content."""
        web_driver = self.driver(url or self.base_url)
        html_content = web_driver.get_html_content(scroll_bottom)
        return BeautifulSoup(html_content, "html.parser")

    def check_image(self, image_url: str) -> bool:
        """Checks if an image exists at the given URL."""
        web_driver = self.driver(image_url)
        return web_driver.check_image_existence()

    def get_categories(self):
        """Fetches and saves categories from Wildberries."""
        url = "https://static-basket-01.wb.ru/vol0/data/main-menu-ru-ru-v2.json"
        soup = self.get_soup(url)
        data = json.loads(soup.find("pre").text) if soup.find("pre") else []
        self.save_categories_by_json(data)

    @transaction.atomic
    def save_categories_by_json(self, data: list) -> None:
        """Recursively saves categories from the JSON data."""
        categories_to_create = []
        category_cache = {}

        for cat in data:
            if (
                not cat.get("parent")
                and int(cat.get("id", 0)) not in settings.CATEGORIES_SOURCE_IDS
            ):
                continue

            category = Category(
                source_id=cat.get("id"),
                title=cat.get("name"),
                slug_name=cat.get("url"),
                shard=cat.get("shard"),
                parent=category_cache.get(cat.get("parent")),
            )
            categories_to_create.append(category)
            category_cache[cat.get("id")] = category

            if cat.get("childs"):
                self.save_categories_by_json(cat.get("childs"))

        Category.objects.bulk_create(categories_to_create, ignore_conflicts=True)

    def get_products(self):
        """Fetches and saves products and their variants."""
        currency = "rub"
        categories = list(Category.objects.all())
        random.shuffle(categories)
        existing_variant_source_ids = set(
            ProductVariant.objects.values_list("source_id", flat=True)
        )

        for category in categories:
            url = (
                f"https://catalog.wb.ru/catalog/{category.shard}/v2/catalog"
                f"?ab_testing=false&appType=1&cat={category.source_id}"
                f"&curr={currency}&dest=491&sort=popular&spp=30&uclusters=0"
            )
            soup = self.get_soup(url)
            data = json.loads(soup.find("pre").text) if soup.find("pre") else {}

            products_data = data.get("data", {}).get("products", [])
            random.shuffle(products_data)
            roots = {}
            for product in products_data:
                roots.setdefault(product["root"], []).append(product)

            for root, products in roots.items():
                self.save_products_and_variants(
                    category, root, products, currency, existing_variant_source_ids
                )

    @transaction.atomic
    def save_products_and_variants(
        self, category, root, products, currency, existing_variant_source_ids
    ):
        """Saves products and their variants in bulk."""
        product_objects = []
        variant_objects = []
        image_objects = []

        for product in products:
            source_id = product["id"]
            if source_id in existing_variant_source_ids:
                continue

            product_object, _ = Product.objects.get_or_create(
                title=product.get("name"),
                defaults={"category": category, "root": int(root)},
            )
            product_objects.append(product_object)

            for pv in product.get("sizes", []):
                variant, _ = ProductVariant.objects.get_or_create(
                    product=product_object,
                    source_id=source_id,
                    defaults={
                        "price": f"{pv.get('price', {}).get('total', 0)} {currency}"
                    },
                )
                variant_objects.append(variant)

                images = self.get_product_variant_images(source_id)
                for img_url in images:
                    image_objects.append(
                        ProductVariantImage(variant=variant, image_link=img_url)
                    )

        ProductVariantImage.objects.bulk_create(image_objects, ignore_conflicts=True)

    def get_product_variant_images(self, source_id):
        """Fetches the image URLs for a product variant."""
        variant_detail_soup = self.get_soup(
            f"https://www.wildberries.ru/catalog/{source_id}/detail.aspx"
        )
        if not variant_detail_soup:
            return []

        swiper = variant_detail_soup.find("ul", {"class": "swiper-wrapper"})
        if not swiper:
            return []

        images = []
        for li in swiper.find_all("li", {"class": "swiper-slide"}):
            div = li.find_next("div", {"class": "slide__content img-plug"})
            if not div:
                continue
            img = div.find_next("img")
            if img and img.get("src"):
                images.append(img["src"])
        return images

    def get_all_product_variant_images(self):
        """Fetches and saves images for all product variants."""
        variants = ProductVariant.objects.all()

        image_objects = []
        for variant in variants:
            images = self.get_product_variant_images(variant.source_id)
            for img_url in images:
                image_objects.append(
                    ProductVariantImage(variant=variant, image_link=img_url)
                )

        if image_objects:
            ProductVariantImage.objects.bulk_create(
                image_objects, ignore_conflicts=True
            )

    def get_product_by_source_id(self, source_id: int) -> Product:
        """Scrapes a product and its variants by the given source_id."""
        currency = "rub"
        url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr={currency}&dest=491&spp=30&ab_testing=false&nm={source_id}"
        soup = self.get_soup(url)
        product_data = json.loads(soup.find("pre").text) if soup.find("pre") else {}

        if not product_data.get("data"):
            print(f"No data found for product with source_id {source_id}")
            return None

        product_info = product_data["data"]["products"][0]
        root = product_info["root"]
        title = product_info["name"]

        product_object, _ = Product.objects.get_or_create(
            root=root,
            defaults={"title": title},
        )

        variant_objects = []
        for size in product_info.get("sizes", []):
            price = size.get("price", {}).get("total", 0)
            product_variant, _ = ProductVariant.objects.get_or_create(
                product=product_object,
                source_id=source_id,
                defaults={"price": f"{price} {currency}"},
            )
            variant_objects.append(product_variant)

            images = self.get_product_variant_images(source_id)
            ProductVariantImage.objects.bulk_create(
                [
                    ProductVariantImage(variant=product_variant, image_link=img)
                    for img in images
                ],
                ignore_conflicts=True,
            )

        return product_object

    def get_product_comments(self):
        """Fetches and saves product comments."""
        products = list(Product.objects.values("root", "id"))
        random.shuffle(products)
        roots = set()

        for product in products:
            root = product["root"]
            if root in roots:
                continue
            roots.add(root)

            url = f"https://feedbacks2.wb.ru/feedbacks/v1/{root}"
            soup = self.get_soup(url)
            data = json.loads(soup.find("pre").text) if soup.find("pre") else {}
            feedbacks = data.get("feedbacks", [])

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

        comment_object, _ = Comment.objects.get_or_create(
            product_id=product_id,
            content=comment.get("text"),
            defaults={
                "rating": comment.get("productValuation", 0),
                "status": CommentStatuses.ACCEPTED,
                "wb_user": comment.get("wbUserDetails", {}).get("name", ""),
            },
        )

        self.save_comment_images(comment_object, comment.get("photo", []))

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

            if (
                link
                and not CommentFiles.objects.filter(
                    comment=comment_object, file_link=link
                ).exists()
            ):
                image_objects.append(
                    CommentFiles(comment=comment_object, file_link=link)
                )

        CommentFiles.objects.bulk_create(image_objects, ignore_conflicts=True)
