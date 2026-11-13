from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .address_lookup import SALT
from .demo import reset_demo
from .demo_addresses import MONTREAL_ADDRESSES
from .models import MenuItem, Order, Restaurant


class CheckoutAddressTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(username="buyer", role="customer")
        owner = User.objects.create_user(username="owner", role="restaurant")
        restaurant = Restaurant.objects.create(name="Kitchen", owner=owner, latitude="45.5", longitude="-73.57")
        item = MenuItem.objects.create(restaurant=restaurant, name="Soup", price="8.00")
        self.payload = {"restaurant_id": restaurant.pk, "items": [{"menu_item_id": item.pk, "quantity": 1}]}
        self.client = APIClient()
        self.client.force_authenticate(self.customer)

    def token(self, index=0, **overrides):
        address, latitude, longitude = MONTREAL_ADDRESSES[index]
        return signing.dumps({"address": address, "latitude": latitude, "longitude": longitude,
                              "customer_id": self.customer.pk, **overrides}, salt=SALT)

    def test_missing_blank_invalid_and_other_customers_address_rejected(self):
        for token in (None, "", "invalid", self.token(customer_id=self.customer.pk + 1)):
            with self.subTest(token=token):
                payload = dict(self.payload)
                if token is not None:
                    payload["delivery_address_token"] = token
                self.assertEqual(self.client.post(reverse("place-order"), payload, format="json").status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_address_saved_to_customer_without_changing_previous_order(self):
        for index in (0, 1):
            response = self.client.post(reverse("place-order"), {
                **self.payload, "delivery_address_token": self.token(index), "delivery_unit": "12",
            }, format="json")
            self.assertEqual(response.status_code, 201, response.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.delivery_address, MONTREAL_ADDRESSES[1][0])
        self.assertEqual(self.customer.delivery_unit, "12")
        self.assertEqual(str(self.customer.delivery_latitude), MONTREAL_ADDRESSES[1][1])
        self.assertEqual(Order.objects.order_by("id").first().delivery_address, MONTREAL_ADDRESSES[0][0])


class DemoSeedTests(TestCase):
    @patch("orders.demo.demo_enabled", return_value=True)
    def test_reset_restores_addresses_and_all_map_colors(self, enabled):
        expected = {"Green Garden": (2, "green"), "Vegan Corner": (4, "amber"),
                    "Plateau Pizza": (7, "red"), "Verdun Bowl": (0, "green"),
                    "Rosemont Tacos": (5, "amber"), "Lachine Bistro": (1, "red")}
        previous_addresses = None
        for _ in range(2):
            result = reset_demo()
            self.assertEqual(result["orders"], 51)
            customers = get_user_model().objects.filter(role="customer").order_by("username")
            addresses = list(customers.values_list("delivery_address", flat=True))
            self.assertEqual(len(set(addresses)), 6)
            if previous_addresses:
                self.assertEqual(addresses, previous_addresses)
            previous_addresses = addresses
            for order in Order.objects.select_related("customer"):
                self.assertEqual(order.delivery_address, order.customer.delivery_address)
                self.assertEqual(order.delivery_latitude, order.customer.delivery_latitude)
                self.assertEqual(order.delivery_longitude, order.customer.delivery_longitude)
            client = APIClient()
            client.force_authenticate(get_user_model().objects.get(username="operator1"))
            response = client.get(reverse("dashboard-map"))
            self.assertEqual(response.status_code, 200)
            actual = {point["label"]: (point["restaurant"]["queued"], point["restaurant"]["queue_color"])
                      for point in response.data["points"] if "restaurant" in point}
            self.assertEqual(actual, expected)

    def test_standard_seed_populates_customer_and_order_addresses(self):
        from io import StringIO
        from django.core.management import call_command

        for restore in (False, True):
            call_command("seed_data", restore_baseline=restore, stdout=StringIO())
            self.assertEqual(get_user_model().objects.filter(role="customer").exclude(delivery_address="").count(), 2)
            self.assertTrue(Order.objects.exists())
            for order in Order.objects.select_related("customer"):
                self.assertTrue(order.delivery_address)
                self.assertEqual(order.delivery_address, order.customer.delivery_address)
                self.assertEqual(order.delivery_latitude, order.customer.delivery_latitude)
