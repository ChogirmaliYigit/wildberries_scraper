from scraper.models import CommentStatuses
from users.utils import send_email


def send_comment_notification(comment):
    if comment.user:
        name = str(
            comment.user.full_name if comment.user.full_name else comment.user.email
        )
        if comment.status == CommentStatuses.NOT_ACCEPTED:
            reason = ""
            if comment.reason:
                reason = f' по причине "{comment.reason}"'
            send_email(
                users=[comment.user.email],
                subject="OZRO",
                message=f"Уважаемый {name}, ваш отзыв отклонен{reason}, исправьте отзыв и отправьте еще раз.",
            )
        elif comment.status == CommentStatuses.ACCEPTED:
            send_email(
                users=[comment.user.email],
                subject="OZRO",
                message=f"Уважаемый {name}, ваш отзыв одобрен, спасибо.",
            )


def send_no_product_message(comment, product_source_id):
    if comment.user:
        send_email(
            users=[comment.user],
            subject="OZRO",
            message=f"Вы ввели неверный артикул ({product_source_id}). Пожалуйста, проверьте и попробуйте еще раз.",
        )
