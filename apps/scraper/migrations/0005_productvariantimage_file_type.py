# Generated by Django 5.0.7 on 2024-08-23 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scraper", "0004_alter_productvariantimage_image_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariantimage",
            name="file_type",
            field=models.CharField(
                choices=[("image", "Image"), ("video", "Video")],
                default="image",
                max_length=20,
            ),
        ),
    ]