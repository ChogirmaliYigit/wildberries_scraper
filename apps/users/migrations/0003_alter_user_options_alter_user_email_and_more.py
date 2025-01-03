# Generated by Django 5.0.7 on 2024-08-19 05:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_userotp_type"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "User", "verbose_name_plural": "Users"},
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                error_messages={
                    "unique": "Пользователь с таким адресом электронной почты уже существует"
                },
                max_length=254,
                unique=True,
                verbose_name="Email",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="full_name",
            field=models.CharField(
                blank=True, max_length=1000, null=True, verbose_name="Full name"
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="is_blocked",
            field=models.BooleanField(default=False, verbose_name="Is blocked"),
        ),
        migrations.AlterField(
            model_name="user",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="users/profile_photos/",
                verbose_name="Profile photo",
            ),
        ),
    ]
