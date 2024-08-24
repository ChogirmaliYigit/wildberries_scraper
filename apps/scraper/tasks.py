from celery import shared_task

from .models import Comment, RequestedComment
from .utils import wildberries


@shared_task
def scrape_product_by_source_id(source_id, comment_id):
    try:
        product = wildberries.get_product_by_source_id(source_id)
        if product and not product.category:
            product.delete()
            product = None
    except Exception as exc:
        product = None
        print(
            f"Exception while scraping product by source id at apps/scraper/tasks.py:8: {exc.__class__.__name__}: {exc}"
        )

    # Retrieve the comment object using its ID
    try:
        comment_object = Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        return

    rc = RequestedComment.objects.filter(id=comment_id + 1)
    if rc.exists():
        rc.delete()

    if product:
        comment_object.product = product
        comment_object.save(update_fields=["product"])
    else:
        comment_object.delete()
