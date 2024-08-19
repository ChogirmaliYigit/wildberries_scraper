import json
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from dateutil.parser import ParserError, parse
from django.conf import settings
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
        """
        returns soup of elements
        """

        web_driver = self.driver(url or self.base_url)
        html_content = web_driver.get_html_content(scroll_bottom)

        soup = BeautifulSoup(html_content, "html.parser")
        return soup

    def check_image(self, image_url: str) -> bool:
        web_driver = self.driver(image_url)
        return web_driver.check_image_existence()

    def get_categories(self):
        soup = self.get_soup(
            "https://static-basket-01.wb.ru/vol0/data/main-menu-ru-ru-v2.json"
        )
        data = json.loads(soup.find("pre").text) if soup.find("pre") else []
        self.save_categories_by_json(data)

    def save_categories_by_json(self, data: list) -> None:
        cat_objects = []
        for cat in data:
            if not int(cat.get("id")) in settings.CATEGORIES_SOURCE_IDS:
                continue
            category = Category(
                source_id=cat.get("id"),
                title=cat.get("name"),
                slug_name=cat.get("url"),
                shard=cat.get("shard"),
                parent=None,
            )
            cat_objects.append(category)
            parent_source_id = cat.get("parent")
            if parent_source_id and str(parent_source_id).isdigit():
                parent = next(
                    (c for c in cat_objects if c.source_id == int(parent_source_id)),
                    None,
                )
                if not parent:
                    parent = Category.objects.filter(
                        source_id=int(parent_source_id)
                    ).first()
                if parent:
                    category.parent = parent
            try:
                category.save()
            except Exception as exc:
                print(
                    f"Exception while saving category instance: {exc.__class__.__name__}: {exc}"
                )
            if cat.get("childs", []):
                self.save_categories_by_json(cat.get("childs", []))

    def get_products(self):
        currency = "rub"

        categories = Category.objects.all()
        product_variant_source_ids = list(
            ProductVariant.objects.values_list("source_id", flat=True)
        )

        for category in categories:
            url = (
                f"https://catalog.wb.ru/catalog/{category.shard}/v2/catalog?ab_testing=false&appType=1"
                f"&cat={category.source_id}&curr={currency}&dest=491&sort=popular&spp=30&uclusters=0"
            )
            soup = self.get_soup(url)
            data = json.loads(soup.find("pre").text) if soup.find("pre") else {}
            roots = {}
            for p in data.get("data", {}).get("products", []):
                root = roots.pop(str(p["root"]), [])
                root.append(p)
                roots[str(p["root"])] = root

            for root, products in roots.items():
                for product in products:
                    source_id = product.get("id")
                    if source_id in product_variant_source_ids:
                        continue
                    product_object, _ = Product.objects.get_or_create(
                        title=product.get("name"),
                        defaults={
                            "category": category,
                            "root": int(root),
                        },
                    )
                    for pv in product.get("sizes", []):
                        product_variant, _ = ProductVariant.objects.get_or_create(
                            product=product_object,
                            source_id=product.get("id"),
                            defaults={
                                "price": f"{pv.get('price', {}).get('total', 0)} {currency}",
                            },
                        )
                        variant_detail_soup = self.get_soup(
                            f"https://www.wildberries.ru/catalog/{source_id}/detail.aspx"
                        )
                        product_variant_images = []
                        if variant_detail_soup:
                            swiper = variant_detail_soup.find(
                                "ul", {"class": "swiper-wrapper"}
                            )
                            if swiper:
                                swiper_lis = swiper.find_all(
                                    "li", {"class": "swiper-slide slide"}
                                )
                                if not swiper_lis:
                                    swiper_lis = []
                                for li in swiper_lis:
                                    img = li.find_next("img")
                                    if img and img["src"]:
                                        product_variant_images.append(
                                            ProductVariantImage(
                                                variant=product_variant,
                                                image_link=img["src"],
                                            )
                                        )
                        ProductVariantImage.objects.bulk_create(
                            product_variant_images, ignore_conflicts=True
                        )

    def get_product_by_source_id(self, source_id: int) -> Product:
        """
        Scrapes a product and its variants by the given source_id
        """
        currency = "rub"

        url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr={currency}&dest=491&spp=30&ab_testing=false&nm={source_id}"
        soup = self.get_soup(url)
        product_data = json.loads(soup.find("pre").text) if soup.find("pre") else {}

        if not product_data.get("data"):
            print(f"No data found for product with source_id {source_id}")
            return

        product_info = product_data["data"]["products"][0]
        root = product_info.get("root")
        title = product_info.get("name")

        product_object, _ = Product.objects.get_or_create(
            root=root,
            defaults={"title": title},
        )

        for size in product_info.get("sizes", []):
            price = size.get("price", {}).get("total", 0)
            product_variant, _ = ProductVariant.objects.get_or_create(
                product=product_object,
                source_id=source_id,
                defaults={"price": f"{price} {currency}"},
            )
            variant_detail_soup = self.get_soup(
                f"https://www.wildberries.ru/catalog/{source_id}/detail.aspx"
            )
            product_variant_images = []
            if variant_detail_soup:
                swiper = variant_detail_soup.find("ul", {"class": "swiper-wrapper"})
                if swiper:
                    swiper_lis = swiper.find_all("li", {"class": "swiper-slide slide"})
                    for li in swiper_lis:
                        img = li.find_next("img")
                        if img and img["src"]:
                            product_variant_images.append(
                                ProductVariantImage(
                                    variant=product_variant, image_link=img["src"]
                                )
                            )
            ProductVariantImage.objects.bulk_create(
                product_variant_images, ignore_conflicts=True
            )
        return product_object

    def get_product_comments(self):
        """
        Product comments list scraper
        """

        products = list(Product.objects.values("root", "id"))
        roots = set()

        for product in products:
            root = product["root"]
            if root in roots:
                continue
            roots.add(root)

            url = f"https://feedbacks2.wb.ru/feedbacks/v1/{root}"
            soup = self.get_soup(url)
            data = json.loads(soup.find("pre").text) if soup.find("pre") else {}
            feedbacks = data.get("feedbacks")
            if not feedbacks:
                continue

            for comment in feedbacks:
                created_date = comment.get("createdDate")
                try:
                    published_date = (
                        parse(created_date, yearfirst=True) if created_date else None
                    )
                except ParserError:
                    published_date = None
                delta = datetime.now(timezone.utc) - timedelta(weeks=2)
                if published_date and (published_date - delta).seconds > 0:
                    comment_object, _ = Comment.objects.get_or_create(
                        product_id=int(product["id"]),
                        content=comment.get("text"),
                        defaults={
                            "rating": comment.get("productValuation", 0),
                            "status": CommentStatuses.ACCEPTED,
                            "wb_user": comment.get("wbUserDetails", {}).get("name", ""),
                        },
                    )
                    for photo_id in comment.get("photo", []):
                        photo_id = str(photo_id)
                        link = None
                        for basket_id in range(1, 11):
                            img_url = f"https://feedback0{basket_id}.wbbasket.ru/vol{photo_id[:4]}/part{photo_id[:6]}/{photo_id}/photos/ms.webp"
                            if self.check_image(img_url):
                                link = img_url
                                break
                        if link:
                            CommentFiles.objects.get_or_create(
                                comment=comment_object,
                                file_link=link,
                            )
