"""Periodic offer expiration and persistent queue recovery."""
from datetime import timedelta
import logging

from django.conf import settings
from django.utils import timezone

from delivery.commands import DeliveryConflict, expire_delivery_offer
from delivery.models import DeliveryAssignment
from .events import dispatcher
from .services import OrderQueueService

logger = logging.getLogger(__name__)


def check_stalled_orders():
    cutoff = timezone.now() - timedelta(seconds=settings.DISPATCH_OFFER_TIMEOUT_SECONDS)
    overdue_ids = list(DeliveryAssignment.objects.filter(
        status=DeliveryAssignment.Status.OFFERED, offered_at__lte=cutoff,
    ).values_list("pk", flat=True))
    expired = 0
    for assignment_id in overdue_ids:
        try:
            expired += expire_delivery_offer(assignment_id=assignment_id, cutoff=cutoff)
        except DeliveryConflict:
            logger.warning("Offer %s changed during expiration; retry next sweep.", assignment_id)
    for order in OrderQueueService().get_waiting_orders():
        dispatcher.offer_to_nearest(order)
    return expired
