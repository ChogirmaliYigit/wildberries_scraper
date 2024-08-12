from bs4 import BeautifulSoup
from django.db.models import Count
from django.utils.text import slugify
from scraper.models import Category, Product, ProductVariant, ProductVariantImage
from unidecode import unidecode

from .driver import WebDriver


class WildberriesClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_soup(self, url: str = None) -> BeautifulSoup:
        """
        returns soup of elements
        """

        web_driver = WebDriver(url or self.base_url)
        html_content = web_driver.get_html_content()

        soup = BeautifulSoup(html_content, "html.parser")
        return soup

    def get_top_level_categories_list(self):
        """
        Top level categories list scraper
        """
        soup = self.get_soup()

        catalog_div = soup.find(
            "div", {"class": "menu-burger__main j-menu-burger-main"}
        )
        catalog_ul = catalog_div.find("ul", {"class": "menu-burger__main-list"})

        catalog_items = catalog_ul.find_all(
            "li", {"class": "menu-burger__main-list-item j-menu-main-item"}
        )
        categories_objects = []
        for item in catalog_items:
            categories_objects.append(
                Category(
                    title=item.find_next("span").text
                    if "<span" in str(item)
                    else item.text,
                    source_id=int(item["data-menu-id"]),
                )
            )
        Category.objects.bulk_create(categories_objects, ignore_conflicts=True)

    def get_sub_categories_by_parent(self):
        """
        Subcategories by parent scraper
        """
        categories = Category.objects.filter()

        for category in categories:
            slug = self.make_category_slug(category)
            tag = (
                "catalog/"
                if category.slug_name != "promotions" or "catalog" not in slug
                else ""
            )
            url = f"{self.base_url}/{tag}{slug}"
            soup = self.get_soup(url)

            content = soup.find("div", {"class": "promo-category-page__content"})
            if not content:
                print(category.title, "--", url)
                return
            cards = content.find_all(
                "a", {"class": "list-category__item j-list-category-item"}
            )
            subcategory_objects = []
            for card in cards:
                subcategory_objects.append(
                    Category(
                        title=card.find("span", {"class": "list-category__title"}).text,
                        image_link=card.find("img")["src"],
                        source_id=0,
                        parent=category,
                        slug_name=card["href"],
                    )
                )
            Category.objects.bulk_create(subcategory_objects, ignore_conflicts=True)

    def get_products_list_by_category(self):
        """
        Products list scrapper
        """
        categories = Category.objects.annotate(
            num_sub_categories=Count("sub_categories")
        ).filter(num_sub_categories=0)
        product_variant_source_ids = ProductVariant.objects.values_list(
            "source_id", flat=True
        )

        for category in categories:
            slug = self.make_category_slug(category)
            tag = (
                ""
                if category.slug_name == "promotions" or "catalog" in slug
                else "/catalog/"
            )
            url = f"{self.base_url}{tag}{slug}"
            soup = self.get_soup(url)

            product_card_list = soup.find("div", {"class": "product-card-list"})
            if not product_card_list:
                print(category.title, "--", url)
                return
            articles = product_card_list.find_all("article", {"class": "product-card"})
            product_objects = []
            for article in articles:
                source_id = int(article.find_next("a")["href"].split("/")[-2])
                if source_id in product_variant_source_ids:
                    continue
                product_detail = self.get_product_detail(article.find_next("a")["href"])
                product = Product(category=category, title=product_detail["title"])
                product_objects.append(product)
                product_variant_objects = []
                for variant in product_detail["variants"]:
                    image_links = variant.pop("image_links")
                    product_variant = ProductVariant(product=product, **variant)
                    product_variant_objects.append(product_variant)
                    product_variant_images = []
                    for link in image_links:
                        product_variant_images.append(
                            ProductVariantImage(
                                variant=product_variant, image_link=link
                            )
                        )
                    ProductVariantImage.objects.bulk_create(
                        product_variant_images, ignore_conflicts=True
                    )
                ProductVariant.objects.bulk_create(
                    product_variant_objects, ignore_conflicts=True
                )
            Product.objects.bulk_create(product_objects, ignore_conflicts=True)

    def get_product_detail(self, link: str) -> dict:
        """
        Get product detail based on its unique id
        """

        soup = self.get_soup(link)
        product_page = soup.find("div", {"class": "product-page__header-wrap"})
        variants = soup.find("div", {"class": "custom-slider__list"}).find_all(
            "div", {"class": "custom-slider__item j-color"}
        )
        variants_data = []
        for variant in variants:
            soup = self.get_soup(variant.find_next("a", {"class": "img-plug"})["href"])
            options = soup.find("div", {"class": "product-page__options"})
            price = soup.find(
                "ins", {"class": "price-block__final-price wallet"}
            ) or soup.find("span", {"class": "sold-out-product__text"})
            variants_data.append(
                {
                    "source_id": int(options.find("span", {"id": "productNmId"}).text),
                    "image_links": [
                        li.find_next("img")["src"]
                        if li.find_next("img")
                        else li.find_next("video")["src"]
                        for li in soup.find("ul", {"class": "swiper-wrapper"}).find_all(
                            "li", {"class": {"swiper-slide slide j-product-photo"}}
                        )
                    ],
                    "color": soup.find("div", {"class": "color-name"})
                    .find_next("span", {"class": "color"})
                    .text,
                    "price": price.text,
                }
            )
        return {
            "title": product_page.find("h1", {"class": "product-page__title"}).text,
            "variants": variants,
        }

    def make_category_slug(self, category: Category, slug: str = "") -> str:
        """
        Make breadcrumb slug for category name
        """

        slug = f"{slug}{category.slug_name if category.slug_name else slugify(unidecode(category.title))}"
        if category.parent and "catalog" not in slug:
            self.make_category_slug(
                category.parent,
                f"{category.parent.slug_name if category.parent.slug_name else slugify(category.parent.title)}/",
            )
        return slug
