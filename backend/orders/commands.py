from abc import ABC, abstractmethod
from django.db import transaction
from django.db.models import Subquery
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import MenuItem, Order, OrderLine, Restaurant


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
        if not self.customer.is_active or self.customer.role != self.customer.Role.CUSTOMER:
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

        for line in order_lines:
            OrderLine.objects.create(order=order, **line)

        return order


class OrderConflict(APIException):
    status_code = 409
    default_detail = "This order has changed. Refresh the board and try again."


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
            pk=order.pk, restaurant__owner=self.actor, status=self.expected_status,
        )

    def conflict(self):
        return OrderConflict()

    def execute(self):
        if not self.actor.is_active or self.actor.role != self.actor.Role.RESTAURANT:
            raise PermissionDenied("Only restaurant accounts can perform this operation.")
        order = get_object_or_404(Order, pk=self.order_id, restaurant__owner=self.actor)
        if order.status != self.expected_status:
            raise OrderConflict()
        try:
            order.transition(self.target_status)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        if not self.eligible_orders(order).update(status=order.status):
            raise self.conflict()
        order.refresh_from_db()
        return order


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


class CancelOrderCommand(RestaurantOrderCommand):
    target_status = Order.Status.CANCELLED


class StartPreparationCommand(RestaurantOrderCommand):
    target_status = Order.Status.PREPARING

    def eligible_orders(self, order):
        queue_head = Order.objects.filter(
            restaurant_id=order.restaurant_id, status=Order.Status.ACCEPTED,
        ).order_by("created_at", "id").values("pk")[:1]
        return super().eligible_orders(order).filter(pk=Subquery(queue_head))

    def conflict(self):
        return OrderConflict("Only the oldest accepted order can start preparing. Refresh the board and prepare the first order in the queue.")


class MarkOrderReadyCommand(RestaurantOrderCommand):
    target_status = Order.Status.READY


class MarkOrderPickedUpCommand(RestaurantOrderCommand):
    target_status = Order.Status.PICKED_UP


RESTAURANT_ORDER_COMMANDS = {
    command.target_status: command
    for command in (
        AcceptOrderCommand, RejectOrderCommand, CancelOrderCommand,
        StartPreparationCommand, MarkOrderReadyCommand, MarkOrderPickedUpCommand,
    )
}
