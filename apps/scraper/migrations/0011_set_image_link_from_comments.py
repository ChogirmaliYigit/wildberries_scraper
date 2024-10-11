from django.db import migrations
from django.db.models import Q


def set_image_links(apps, schema_editor):
    Product = apps.get_model("scraper", "Product")

    for product in Product.objects.all():
        first_valid_comment = product.product_comments.filter(
            Q(file__isnull=False, file_type="image")
            | Q(files__isnull=False, files__file_type="image"),
            status="accepted",
            content__isnull=False,
        ).first()

        if first_valid_comment:
            # If a file exists, use its URL
            if first_valid_comment.file:
                product.image_link = first_valid_comment.file.url
                product.save(update_fields=["image_link"])
            else:
                # If no file, try to get the first valid related CommentFile
                first_comment_file = first_valid_comment.files.filter(
                    file_type="image"
                ).first()
                if first_comment_file:
                    product.image_link = (
                        first_comment_file.file_link
                    )  # Adjust this based on your actual field name
                    product.save(update_fields=["image_link"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "scraper",
            "0010_alter_category_created_at_alter_category_deleted_at_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(set_image_links),
    ]
