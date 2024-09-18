from users.utils import send_email


def send_comment_notification(comment):
    from scraper.models import CommentStatuses

    if comment.user:
        if comment.status == CommentStatuses.NOT_ACCEPTED:
            reason = ""
            if comment.reason:
                reason = f' по причине "{comment.reason}"'
            send_email(
                users=[comment.user.email],
                subject=f"№{comment.pk} Статус обратной связи",
                message=f"Дорогой {str(comment.user.full_name if comment.user.full_name else comment.user.email)}! Ваш отзыв №{comment.pk} не принят{reason}. Пожалуйста, дважды проверьте свой комментарий, а затем отправьте нам его еще раз для проверки.",
            )
        elif comment.status == CommentStatuses.ACCEPTED:
            send_email(
                users=[comment.user.email],
                subject=f"№{comment.pk} Accepted",
                message="Otziv accepted",
            )
