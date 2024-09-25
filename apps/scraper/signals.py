from django.db.models.signals import post_save
from django.dispatch import receiver
from scraper.models import Comment, CommentStatuses
from scraper.utils import wildberries
from scraper.utils.notify import send_comment_notification, send_no_product_message


@receiver(post_save, sender=Comment)
def send_email_to_user(sender, instance, **kwargs):
    send_comment_notification(instance)
    if (
        instance.product_source_id
        and not instance.product
        and instance.status == CommentStatuses.ACCEPTED
    ):
        product = wildberries.get_product_by_source_id(instance.product_source_id)
        if product:
            instance.product = product
            instance.save(update_fields=["product"])
        else:
            send_no_product_message(instance, instance.product_source_id)
            instance.delete()
