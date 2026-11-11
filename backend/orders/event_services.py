from django.db import transaction
from django.db.models import Max
from .models import Order, OrderStatusEvent


@transaction.atomic
def record_order_status_event(order, from_status, to_status, actor=None):
    if from_status == to_status:
        return None

    # Lock the order while assigning its next transition number.
    locked_order = Order.objects.select_for_update().get(pk=order.pk)

    last_number = (
        OrderStatusEvent.objects
        .filter(order=locked_order)
        .aggregate(max_number=Max("transition_number"))["max_number"]
        or 0
    )

    actor_username = actor.username if actor else ""
    actor_role = getattr(actor, "role", "") if actor else ""

    return OrderStatusEvent.objects.create(
        order=locked_order,
        transition_number=last_number + 1,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        actor_username=actor_username,
        actor_role=actor_role,
    )