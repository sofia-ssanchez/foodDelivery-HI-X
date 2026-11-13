from django.utils import timezone

from .models import DeliveryAssignment


def invalidate_offers_for_cancelled_order(*, order_id):
    """Close pending offers when ORD cancels an order.

    Accepted assignments are deliberately left alone: DLV's reassignment and
    accepted-delivery policy remains separate from this pending-offer cleanup.
    Call from ORD's existing transaction after the order reaches cancelled.
    """
    return DeliveryAssignment.objects.filter(
        order_id=order_id,
        status=DeliveryAssignment.Status.OFFERED,
    ).update(
        status=DeliveryAssignment.Status.CANCELLED,
        cancelled_at=timezone.now(),
    )
