from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from scraper.models import Comment, CommentStatuses
from users.utils import send_email


@receiver(post_save, sender=Comment)
def update_comment_status(sender, instance, created, **kwargs):
	if not created and instance.user and instance.status == CommentStatuses.NOT_ACCEPTED and not settings.DEBUG:
		send_email(
			users=[instance.user],
			subject=f"#{instance.pk} feedback status",
			message=f"Dear {instance.user.full_name if instance.user.full_name else instance.user.email}!\n\nYour #{instance.pk} feedback is not accepted. Please double-check your comment and then send us again to check."
		)
