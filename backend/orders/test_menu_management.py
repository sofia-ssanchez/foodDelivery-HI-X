from decimal import Decimal

from django.http import Http404
from django.core import signing
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from orders.commands import (
    CreateMenuItemCommand,
    PlaceOrderCommand,
    UpdateMenuItemCommand,
)
from orders.models import MenuItem, Order, OrderLine, Restaurant
from orders.address_lookup import SALT


class RestaurantMenuCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="menu-owner",
            password="password",
            role=User.Role.RESTAURANT,
        )
        self.other_owner = User.objects.create_user(
            username="other-owner",
            password="password",
            role=User.Role.RESTAURANT,
        )
        self.customer = User.objects.create_user(
            username="menu-customer",
            password="password",
            role=User.Role.CUSTOMER,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Owner Restaurant",
            latitude=Decimal("45.500000"),
            longitude=Decimal("-73.560000"),
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.other_owner,
            name="Other Restaurant",
            latitude=Decimal("45.510000"),
            longitude=Decimal("-73.570000"),
        )
        self.client = APIClient()

    def test_owner_can_create_and_update_item_fields(self):
        item = CreateMenuItemCommand(
            actor=self.owner,
            restaurant_id=self.restaurant.id,
            name="Soup",
            price=Decimal("8.25"),
            status=MenuItem.Status.AVAILABLE,
        ).execute()

        updated = UpdateMenuItemCommand(
            actor=self.owner,
            restaurant_id=self.restaurant.id,
            menu_item_id=item.id,
            changes={
                "name": "Tomato Soup",
                "price": Decimal("9.50"),
                "status": MenuItem.Status.SOLD_OUT,
            },
        ).execute()

        self.assertEqual(updated.name, "Tomato Soup")
        self.assertEqual(updated.price, Decimal("9.50"))
        self.assertEqual(updated.status, MenuItem.Status.SOLD_OUT)

    def test_menu_commands_reject_non_restaurant_and_non_owner(self):
        with self.assertRaises(PermissionDenied):
            CreateMenuItemCommand(
                actor=self.customer,
                restaurant_id=self.restaurant.id,
                name="Soup",
                price=Decimal("8.25"),
                status=MenuItem.Status.AVAILABLE,
            ).execute()

        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Soup",
            price=Decimal("8.25"),
        )
        with self.assertRaises(Http404):
            UpdateMenuItemCommand(
                actor=self.other_owner,
                restaurant_id=self.restaurant.id,
                menu_item_id=item.id,
                changes={"price": Decimal("9.50")},
            ).execute()

    def test_duplicate_name_is_rejected_for_same_restaurant(self):
        MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Soup",
            price=Decimal("8.25"),
        )

        with self.assertRaises(ValidationError):
            CreateMenuItemCommand(
                actor=self.owner,
                restaurant_id=self.restaurant.id,
                name="Soup",
                price=Decimal("9.00"),
                status=MenuItem.Status.AVAILABLE,
            ).execute()

    def test_menu_api_restricts_create_and_update_to_owner(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Soup",
            price=Decimal("8.25"),
        )
        self.client.force_authenticate(self.other_owner)

        create_response = self.client.post(
            f"/api/restaurants/{self.restaurant.id}/menu/",
            {"name": "Salad", "price": "7.00"},
            format="json",
        )
        update_response = self.client.patch(
            f"/api/restaurants/{self.restaurant.id}/menu/{item.id}/",
            {"price": "9.00"},
            format="json",
        )

        self.assertEqual(create_response.status_code, 404)
        self.assertEqual(update_response.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("8.25"))

    def test_owner_can_create_and_edit_menu_item_through_api(self):
        self.client.force_authenticate(self.owner)
        create_response = self.client.post(
            f"/api/restaurants/{self.restaurant.id}/menu/",
            {"name": "Soup", "price": "8.25"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["status"], MenuItem.Status.AVAILABLE)

        item_id = create_response.data["id"]
        update_response = self.client.patch(
            f"/api/restaurants/{self.restaurant.id}/menu/{item_id}/",
            {
                "name": "Tomato Soup",
                "price": "9.50",
                "status": MenuItem.Status.SOLD_OUT,
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["name"], "Tomato Soup")
        self.assertEqual(update_response.data["price"], "9.50")
        self.assertEqual(update_response.data["status"], MenuItem.Status.SOLD_OUT)

    def test_restaurant_menu_read_does_not_expose_other_owners_menu(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/restaurants/{self.other_restaurant.id}/menu/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_customer_sees_sold_out_item_but_cannot_order_it(self):
        sold_out = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Seasonal Soup",
            price=Decimal("8.25"),
            status=MenuItem.Status.SOLD_OUT,
        )
        self.client.force_authenticate(self.customer)
        address_token = signing.dumps(
            {
                "customer_id": self.customer.pk,
                "address": "123 Demo Street, Montreal, QC",
                "latitude": "45.500000",
                "longitude": "-73.560000",
            },
            salt=SALT,
        )

        menu_response = self.client.get(
            f"/api/restaurants/{self.restaurant.id}/menu/"
        )
        order_response = self.client.post(
            "/api/orders/",
            {
                "restaurant_id": self.restaurant.id,
                "items": [{"menu_item_id": sold_out.id, "quantity": 1}],
                "delivery_address_token": address_token,
            },
            format="json",
        )

        self.assertEqual(menu_response.status_code, 200)
        self.assertEqual(menu_response.data[0]["status"], MenuItem.Status.SOLD_OUT)
        self.assertEqual(order_response.status_code, 400)
        self.assertIn("Seasonal Soup is currently sold out.", str(order_response.data))
        self.assertEqual(Order.objects.count(), 0)

    def test_price_change_does_not_rewrite_existing_order_line(self):
        item = MenuItem.objects.create(
            restaurant=self.restaurant,
            name="Bowl",
            price=Decimal("12.00"),
        )
        order = PlaceOrderCommand(
            customer=self.customer,
            restaurant_id=self.restaurant.id,
            items=[{"menu_item_id": item.id, "quantity": 2}],
            delivery_address_token=signing.dumps(
                {
                    "customer_id": self.customer.pk,
                    "address": "123 Demo Street, Montreal, QC",
                    "latitude": "45.500000",
                    "longitude": "-73.560000",
                },
                salt=SALT,
            ),
        ).execute()

        UpdateMenuItemCommand(
            actor=self.owner,
            restaurant_id=self.restaurant.id,
            menu_item_id=item.id,
            changes={"price": Decimal("14.00")},
        ).execute()

        line = OrderLine.objects.get(order=order, menu_item=item)
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal("14.00"))
        self.assertEqual(line.unit_price, Decimal("12.00"))
