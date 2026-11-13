from abc import ABC, abstractmethod
from django.db import transaction
from django.db.models import Subquery
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import (
    APIException,
    PermissionDenied,
    ValidationError,
)
from pricing.services import record_order_ledger
from .event_services import record_order_status_event
from delivery import events
from delivery.models import DeliveryAssignment
from delivery.services import invalidate_offers_for_cancelled_order
from .models import MenuItem, Order, OrderLine, Restaurant
from .dispatch.events import order_ready_publisher


class OrderCommand(ABC):
    @abstractmethod
    def execute(self):
        raise NotImplementedError


class PlaceOrderCommand(OrderCommand):
    def __init__(self, customer, restaurant_id, items):
        self.customer = customer
        self.restaurant_id = restaurant_id
        self.items = items

    @transaction.atomic
    def execute(self):
        if (
            not self.customer.is_active
            or self.customer.role != self.customer.Role.CUSTOMER
        ):
            raise PermissionDenied("Only customers can place orders.")

        try:
            restaurant = Restaurant.objects.get(id=self.restaurant_id)
        except Restaurant.DoesNotExist:
            raise ValidationError("Restaurant does not exist.")

        if restaurant.status != Restaurant.Status.OPEN:
            raise ValidationError("Restaurant is not open for orders.")

        order_lines = []

        for item in self.items:
            try:
                menu_item = MenuItem.objects.get(
                    id=item["menu_item_id"],
                    restaurant=restaurant,
                )
            except MenuItem.DoesNotExist:
                raise ValidationError(
                    "Menu item does not belong to this restaurant."
                )

            if menu_item.status != MenuItem.Status.AVAILABLE:
                raise ValidationError(
                    f"{menu_item.name} is currently sold out."
                )

            order_lines.append(
                {
                    "menu_item": menu_item,
                    "quantity": item["quantity"],
                    "unit_price": menu_item.price,
                }
            )

        order = Order.objects.create(
            customer=self.customer,
            restaurant=restaurant,
            status=Order.Status.PLACED,
        )

        # Record the initial order placement.
        record_order_status_event(
            order=order,
            from_status="",
            to_status=Order.Status.PLACED,
            actor=self.customer,
        )

        for line in order_lines:
            OrderLine.objects.create(order=order, **line)

        return order


class OrderConflict(APIException):
    status_code = 409
    default_detail = (
        "This order has changed. Refresh the board and try again."
    )


class RestaurantOrderCommand(OrderCommand):
    @property
    @abstractmethod
    def target_status(self):
        raise NotImplementedError

    def __init__(self, actor, order_id, expected_status):
        self.actor = actor
        self.order_id = order_id
        self.expected_status = expected_status

    def eligible_orders(self, order):
        return Order.objects.filter(
            pk=order.pk,
            restaurant__owner=self.actor,
            status=self.expected_status,
        )

    def conflict(self):
        return OrderConflict()

    @transaction.atomic
    def execute(self):
        if (
            not self.actor.is_active
            or self.actor.role != self.actor.Role.RESTAURANT
        ):
            raise PermissionDenied(
                "Only restaurant accounts can perform this operation."
            )

        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=self.order_id,
            restaurant__owner=self.actor,
        )

        if order.status != self.expected_status:
            raise OrderConflict()

        previous_status = order.status

        try:
            order.transition(self.target_status)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        if not self.eligible_orders(order).update(status=order.status):
            raise self.conflict()

        order.refresh_from_db()

        # Record the successful status transition.
        record_order_status_event(
            order=order,
            from_status=previous_status,
            to_status=order.status,
            actor=self.actor,
        )

        # Record the order in PRC's ledger if it reached a final state.
        if order.status in [
            Order.Status.DELIVERED,
            Order.Status.REJECTED,
            Order.Status.CANCELLED,
        ]:
            record_order_ledger(order)

        if order.status == Order.Status.CANCELLED:
            invalidate_offers_for_cancelled_order(order_id=order.id)

        if order.status == Order.Status.READY:
            transaction.on_commit(
                lambda: events.order_became_ready.send_robust(
                    sender=Order, order_id=order.id
                )
            )

        return order


class CourierOrderCommand(OrderCommand):
class PlacedQueueCommand(RestaurantOrderCommand):
    def eligible_orders(self, order):
        queue_head = Order.objects.filter(
            restaurant_id=order.restaurant_id, status=Order.Status.PLACED,
        ).order_by("created_at", "id").values("pk")[:1]
        return super().eligible_orders(order).filter(pk=Subquery(queue_head))

    def conflict(self):
        return OrderConflict("Only the oldest placed order can be accepted or declined. Refresh the board and handle the first order in the queue.")


class AcceptOrderCommand(PlacedQueueCommand):
    target_status = Order.Status.ACCEPTED


class RejectOrderCommand(PlacedQueueCommand):
    target_status = Order.Status.REJECTED


class CancelOrderCommand(OrderCommand):
    """Shared atomic cancellation path for customer and operator commands."""

    allowed_statuses = ()

    def __init__(self, actor, order_id, expected_status):
        self.actor = actor
        self.order_id = order_id
        self.expected_status = expected_status

    def order_queryset(self):
        return Order.objects.all()

    def eligible_orders(self, order):
        return self.order_queryset().filter(
            pk=order.pk,
            status=self.expected_status,
        ).exclude(
            delivery_assignments__status=DeliveryAssignment.Status.ACCEPTED,
        )

    @transaction.atomic
    def execute(self):
        if (
            not self.actor.is_active
            or self.actor.role != self.actor.Role.COURIER
        ):
            raise PermissionDenied(
                "Only courier accounts can perform this operation."
            )

        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=self.order_id,
            status=self.expected_status,
            # Keep your existing courier assignment relationship here.
        )
        if order.status != self.expected_status or order.status not in self.allowed_statuses:
            raise OrderConflict("This order cannot be cancelled in its current state.")

        if DeliveryAssignment.objects.filter(
            order=order,
            status=DeliveryAssignment.Status.ACCEPTED,
        ).exists():
            raise OrderConflict(
                "This order cannot be cancelled after a courier has accepted it."
            )

        previous_status = order.status

        try:
            order.transition(Order.Status.CANCELLED)
        except ValueError as exc:
            raise OrderConflict(str(exc)) from exc

        order.save(update_fields=["status"])

        # Record the successful status transition.
        record_order_status_event(
            order=order,
            from_status=previous_status,
            to_status=order.status,
            actor=self.actor,
        )

        if order.status == Order.Status.DELIVERED:
            record_order_ledger(order)
        if not self.eligible_orders(order).update(status=Order.Status.CANCELLED):
            raise OrderConflict("This order has changed. Refresh and try again.")

        order.refresh_from_db()
        record_order_ledger(order)
        invalidate_offers_for_cancelled_order(order_id=order.id)
        return order


class DeliverOrderCommand(CourierOrderCommand):
    target_status = Order.Status.DELIVERED


class PlacedQueueCommand(RestaurantOrderCommand):
    def eligible_orders(self, order):
        queue_head = (
            Order.objects.filter(
                restaurant_id=order.restaurant_id,
                status=Order.Status.PLACED,
            )
            .order_by("created_at", "id")
            .values("pk")[:1]
        )

        return (
            super()
            .eligible_orders(order)
            .filter(pk=Subquery(queue_head))
        )

    def conflict(self):
        return OrderConflict(
            "Only the oldest placed order can be accepted or declined. "
            "Refresh the board and handle the first order in the queue."
        )


class AcceptOrderCommand(PlacedQueueCommand):
    target_status = Order.Status.ACCEPTED

class CustomerCancelOrderCommand(CancelOrderCommand):
    actor_role = "customer"
    permission_message = "Only customers can cancel their own orders."
    allowed_statuses = (Order.Status.PLACED,)

    def order_queryset(self):
        return Order.objects.filter(customer=self.actor)


class OperatorCancelOrderCommand(CancelOrderCommand):
    actor_role = "operator"
    permission_message = "Only operators can cancel orders after placement."
    allowed_statuses = (
        Order.Status.ACCEPTED,
        Order.Status.PREPARING,
        Order.Status.READY,
    )


class StartPreparationCommand(RestaurantOrderCommand):
    target_status = Order.Status.PREPARING

    def eligible_orders(self, order):
        queue_head = (
            Order.objects.filter(
                restaurant_id=order.restaurant_id,
                status=Order.Status.ACCEPTED,
            )
            .order_by("created_at", "id")
            .values("pk")[:1]
        )

        return (
            super()
            .eligible_orders(order)
            .filter(pk=Subquery(queue_head))
        )

    def conflict(self):
        return OrderConflict(
            "Only the oldest accepted order can start preparing. "
            "Refresh the board and prepare the first order in the queue."
        )


class MarkOrderReadyCommand(RestaurantOrderCommand):
    target_status = Order.Status.READY

    @transaction.atomic
    def execute(self):
        order = super().execute()
        transaction.on_commit(lambda: order_ready_publisher.notify(order))
        return order


RESTAURANT_ORDER_COMMANDS = {
    command.target_status: command
    for command in (
        AcceptOrderCommand,
        RejectOrderCommand,
        CancelOrderCommand,
        StartPreparationCommand,
        MarkOrderReadyCommand,
        MarkOrderPickedUpCommand,
    )
}


COURIER_ORDER_COMMANDS = {
    DeliverOrderCommand.target_status: DeliverOrderCommand,
}
        AcceptOrderCommand, RejectOrderCommand,
        StartPreparationCommand, MarkOrderReadyCommand,
    )
}
