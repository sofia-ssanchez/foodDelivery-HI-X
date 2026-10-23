from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import MenuItem, Order, OrderLine, Restaurant


class PlaceOrderCommand:
    def __init__(self, customer, restaurant_id, items):
        self.customer = customer
        self.restaurant_id = restaurant_id
        self.items = items

    @transaction.atomic
    def execute(self):
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


class UpdateOrderStatusCommand: