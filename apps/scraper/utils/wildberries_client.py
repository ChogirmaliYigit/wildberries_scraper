import random
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse
from django.db import transaction
from django.db.models import Count, Q
from fake_useragent import UserAgent
from scraper.models import (
    Category,
    Comment,
    CommentFiles,
    CommentStatuses,
    FileTypeChoices,
    Product,
    ProductVariant,
    ProductVariantImage,
)


class WildberriesClient:
    def __init__(self):
        self.ua = UserAgent()

    def get_headers(self, url):
        return {
            "User-Agent": self.ua.random,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "application/json; charset=utf-8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": url,
        }

    def send_request(self, url):
        data = {}
        try:
            response = requests.get(
                url,
                headers=self.get_headers(url),
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except requests.exceptions.JSONDecodeError:
                    data = {}
        except requests.exceptions.SSLError:
            pass
        return data

    def get_soup(
        self, url: str = None, image: bool = False
    ) -> BeautifulSoup | None | str:
        """Returns a BeautifulSoup object of the requested URL's HTML content."""
        try:
            response = requests.get(url, headers=self.get_headers(url))
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type and image:
                return "image"
            if response.status_code != 200:
                return None
        except requests.exceptions.ConnectionError:
            return None
        return BeautifulSoup(response.text, "html.parser")

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
        top_categories = list(Category.objects.filter(parent__isnull=True))
        random.shuffle(top_categories)

        # Step 2: Fetch Wildberries categories data
        wildberries_categories = self.send_request(
            "https://static-basket-01.wb.ru/vol0/data/main-menu-ru-ru-v2.json"
        )

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
                    name=subcategory_name, parent=top_category
                ).first()

                # Handle duplicate subcategory names by appending the top-level category name
                if existing_subcategory:
                    subcategory_name = f"{subcategory_name} {top_category.name}"

                Category.objects.update_or_create(
                    source_id=subcategory["id"],
                    defaults={
                        "title": subcategory_name,
                        "slug_name": subcategory["url"],
                        "shard": subcategory["shard"],
                        "parent": top_category,
                    },
                )

    def get_products(self):
        """Fetches and saves products and their variants."""
        currency = "rub"
        categories = list(set(Category.objects.all()))
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
            data = self.send_request(url)

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
        source_id = str(source_id)
        images = []
        split_options = [
            (2, 5),
            (2, 6),
            (3, 5),
            (3, 6),
            (4, 5),
            (4, 6),
            (5, 5),
            (5, 6),
        ]
        for option in split_options:
            for basket_id in range(1, 20):
                img_url = f"https://basket-0{basket_id}.wbbasket.ru/vol{source_id[:option[0]]}/part{source_id[:option[1]]}/{source_id}/images/c246x328/{basket_id}.webp"
                if self.check_image(img_url):
                    images.append(img_url)
        return images

    def get_all_product_variant_images(self):
        """Fetches and saves images for product variants which there is no image yet."""
        variants = list(
            ProductVariant.objects.annotate(
                images_count=Count(
                    "images", distinct=True, filter=Q(images__isnull=False)
                )
            ).filter(images_count__gt=0)
        )
        random.shuffle(variants)

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
        anchor_tag = breadcrumbs[-2].find_next("a", {"class": "breadcrumbs__link"})
        if not anchor_tag:
            return None
        category = Category.objects.filter(slug_name=anchor_tag["href"]).last()
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
            print(f"No data found for product with source_id {source_id}")
            return None

        product_info = product_data["data"]["products"][0]
        root = product_info["root"]
        title = product_info["name"]

        category = self.get_product_category(source_id)
        if not category:
            return None

        product_object, _ = Product.objects.get_or_create(
            root=root,
            defaults={"title": title, "category": category},
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
                        defaults={
                            "file_link": link,
                            "file_type": FileTypeChoices.VIDEO,
                        },
                    )
                    return True
        return False
