from django.conf import settings
from scraper.models import CommentStatuses
from users.utils import send_email


def send_comment_notification(comment):
    if (
        comment.user
        and comment.status == CommentStatuses.NOT_ACCEPTED
        and not settings.DEBUG
    ):
        send_email(
            users=[comment.user.email],
            subject=f"№{comment.pk} Статус обратной связи",
            message=rf"Дорогой {str(comment.user.full_name if comment.user.full_name else comment.user.email)}!\n\nВаш отзыв №{comment.pk} не принят. Пожалуйста, дважды проверьте свой комментарий, а затем отправьте нам его еще раз для проверки.",
        )
