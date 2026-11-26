"""Shared server-side cart validation for quotes and placed orders."""
from rest_framework.exceptions import ValidationError
from .models import MenuItem, Restaurant


def get_checkout_restaurant(restaurant_id):
    try:
        restaurant = Restaurant.objects.get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        raise ValidationError("Restaurant does not exist.")

    if restaurant.status != Restaurant.Status.OPEN:
        raise ValidationError("Restaurant is not open for orders.")

    return restaurant


def prepare_checkout_lines(restaurant, items):
    order_lines = []

    for item in items:
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

    return order_lines

