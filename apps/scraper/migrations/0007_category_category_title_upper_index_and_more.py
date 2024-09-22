# Generated by Django 5.0.8 on 2024-09-22 17:11

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraper", "0006_comment_product_source_id_alter_comment_promo_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="category",
            index=models.Index(
                django.db.models.functions.text.Upper("title"),
                name="category_title_upper_index",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                django.db.models.functions.text.Upper("title"),
                name="product_title_upper_index",
            ),
        ),
    ]
