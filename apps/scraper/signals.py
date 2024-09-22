from django.db.models.signals import post_save
from django.dispatch import receiver
from scraper.models import Comment
from scraper.utils import wildberries
from scraper.utils.notify import send_comment_notification


@receiver(post_save, sender=Comment)
def send_email_to_user(sender, instance, created, **kwargs):
    send_comment_notification(instance)
    print("Comment signal received")
    if instance.product_source_id and not instance.product:
        print(instance.product_source_id, instance.product)
        product = wildberries.get_product_by_source_id(instance.product_source_id)
        instance.product = product
        instance.save(update_fields=["product"])
