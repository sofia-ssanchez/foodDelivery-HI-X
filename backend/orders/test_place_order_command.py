from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .address_lookup import SALT
from .commands import PlaceOrderCommand
from .models import MenuItem, Order, OrderLine, OrderStatusEvent, Restaurant


class PlaceOrderCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.customer = User.objects.create_user(
            username="test_customer", role="customer"
        )
        self.owner = User.objects.create_user(
            username="test_owner", role="restaurant"
        )
        self.restaurant = Restaurant.objects.create(
            name="Test Kitchen",
            owner=self.owner,
            latitude="45.500000",
            longitude="-73.570000"
        )
        self.burger = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Burger",
            price="12.00"
        )
        self.fries = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Fries",
            price="5.00"
        )
        self.address = "100 Test Street, Montreal"
        self.token = signing.dumps(
            {
                "address": self.address,
                "latitude": "45.500000",
                "longitude": "-73.570000",
                "customer_id": self.customer.pk
            },
            salt=SALT
        )
        self.items = [
            {"menu_item_id": self.burger.pk, "quantity": 2},
            {"menu_item_id": self.fries.pk, "quantity": 1}
        ]

    def place_order(self, **overrides):
        parameters = {
            "customer": self.customer,
            "restaurant_id": self.restaurant.pk,
            "items": self.items,
            "delivery_address_token": self.token,
            "delivery_unit": "12"
        }
        parameters.update(overrides)
        return PlaceOrderCommand(**parameters).execute()

    def assert_no_order_created(self):
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderLine.objects.count(), 0)
        self.assertEqual(OrderStatusEvent.objects.count(), 0)

    def test_valid_order_created(self):
        order = self.place_order()

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.restaurant, self.restaurant)
        self.assertEqual(order.status, Order.Status.PLACED)

    def test_multiple_order_lines_created(self):
        order = self.place_order()

        self.assertEqual(order.lines.count(), 2)

        burger_line = order.lines.get(menu_item=self.burger)
        fries_line = order.lines.get(menu_item=self.fries)

        self.assertEqual(burger_line.quantity, 2)
        self.assertEqual(burger_line.unit_price, Decimal("12.00"))
        self.assertEqual(fries_line.quantity, 1)
        self.assertEqual(fries_line.unit_price, Decimal("5.00"))

    def test_inactive_customer_rejected(self):
        self.customer.is_active = False
        self.customer.save()

        with self.assertRaisesMessage(
            PermissionDenied, "Only customers can place orders."
        ):
            self.place_order()

        self.assert_no_order_created()

    def test_restaurant_account_cannot_place_order(self):
        with self.assertRaisesMessage(
            PermissionDenied, "Only customers can place orders."
        ):
            self.place_order(customer=self.owner)

        self.assert_no_order_created()

    def test_nonexistent_restaurant_rejected(self):
        with self.assertRaisesMessage(
            ValidationError, "Restaurant does not exist."
        ):
            self.place_order(restaurant_id=999999)

        self.assert_no_order_created()

    def test_closed_restaurant_rejected(self):
        self.restaurant.status = Restaurant.Status.CLOSED
        self.restaurant.save()

        with self.assertRaisesMessage(
            ValidationError, "Restaurant is not open for orders."
        ):
            self.place_order()

        self.assert_no_order_created()

    def test_paused_restaurant_rejected(self):
        self.restaurant.status = Restaurant.Status.PAUSED
        self.restaurant.save()

        with self.assertRaisesMessage(
            ValidationError, "Restaurant is not open for orders."
        ):
            self.place_order()

        self.assert_no_order_created()

    def test_item_from_another_restaurant_rejected(self):
        other_restaurant = Restaurant.objects.create(
            name="Other Kitchen",
            owner=self.owner,
            latitude="45.510000",
            longitude="-73.580000"
        )
        other_item = MenuItem.objects.create(
            restaurant=other_restaurant,
            name="Pizza",
            price="15.00"
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Menu item does not belong to this restaurant."
        ):
            self.place_order(
                items=[{"menu_item_id": other_item.pk, "quantity": 1}]
            )

        self.assert_no_order_created()

    def test_sold_out_item_rejected(self):
        self.fries.status = MenuItem.Status.SOLD_OUT
        self.fries.save()

        with self.assertRaisesMessage(
            ValidationError, "Fries is currently sold out."
        ):
            self.place_order()

        self.assert_no_order_created()

    def test_invalid_address_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Find and select your delivery address at checkout before placing the order."
        ):
            self.place_order(delivery_address_token="invalid")

        self.assert_no_order_created()

    def test_customer_address_updated(self):
        order = self.place_order()
        self.customer.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.delivery_address, self.address)
        self.assertEqual(order.delivery_unit, "12")
        self.assertEqual(order.delivery_latitude, Decimal("45.500000"))
        self.assertEqual(order.delivery_longitude, Decimal("-73.570000"))

        self.assertEqual(self.customer.delivery_address, order.delivery_address)
        self.assertEqual(self.customer.delivery_unit, order.delivery_unit)
        self.assertEqual(self.customer.delivery_latitude, order.delivery_latitude)
        self.assertEqual(self.customer.delivery_longitude, order.delivery_longitude)

    def test_order_preserves_original_menu_price(self):
        order = self.place_order()

        self.burger.price = Decimal("15.00")
        self.burger.save()

        line = order.lines.get(menu_item=self.burger)

        self.assertEqual(line.unit_price, Decimal("12.00"))

    def test_initial_status_event_recorded(self):
        order = self.place_order()

        self.assertEqual(order.status_events.count(), 1)

        event = order.status_events.get()

        self.assertEqual(event.from_status, "")
        self.assertEqual(event.to_status, Order.Status.PLACED)
        self.assertEqual(event.transition_number, 1)
        self.assertEqual(event.actor, self.customer)
        self.assertEqual(event.actor_username, self.customer.username)
        self.assertEqual(event.actor_role, "customer")
        self.assertEqual(event.event_id, f"evt-{order.pk}-1")

    def test_order_creation_rolled_back_on_failure(self):
        original_create = OrderLine.objects.create

        def create_line(**kwargs):
            if kwargs["menu_item"] == self.fries:
                raise RuntimeError("Order line creation failed")
            return original_create(**kwargs)

        with patch(
            "orders.commands.OrderLine.objects.create",
            side_effect=create_line
        ):
            with self.assertRaisesMessage(
                RuntimeError, "Order line creation failed"
            ):
                self.place_order()

        self.assert_no_order_created()

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.delivery_address, "")
        self.assertEqual(self.customer.delivery_unit, "")
        self.assertIsNone(self.customer.delivery_latitude)
        self.assertIsNone(self.customer.delivery_longitude)
