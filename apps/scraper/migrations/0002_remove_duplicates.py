# Generated by Django 5.0.7 on 2024-08-28 06:16

from django.db import migrations, models


def remove_duplicates(apps, schema_editor):
    CommentFiles = apps.get_model("scraper", "CommentFiles")
    duplicates = (
        CommentFiles.objects.values("file_link", "comment", "file_type")
        .annotate(count=models.Count("id"))
        .filter(count__gt=1)
    )

    for duplicate in duplicates:
        objects = CommentFiles.objects.filter(
            file_link=duplicate["file_link"],
            file_type=duplicate["file_type"],
            comment=duplicate["comment"],
        ).order_by("id")
        for obj in objects[1:]:
            obj.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("scraper", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remove_duplicates),
    ]
