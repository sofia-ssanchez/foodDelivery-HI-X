from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from rest_framework.test import APIClient
from orders.address_lookup import SALT
from orders.models import MenuItem, Order, Restaurant
from pricing.models import OrderLedger
from pricing.services import (calculate_order_pricing, record_order_ledger,
                              submit_refund_request, decide_refund_request)
from rest_framework.exceptions import ValidationError
from orders.models import OrderLine


class PromoCheckoutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.customer = User.objects.create_user(username="promo-buyer", role="customer")
        self.owner = User.objects.create_user(username="promo-owner", role="restaurant")
        self.operator = User.objects.create_user(username="promo-operator", role="operator")
        self.restaurant = Restaurant.objects.create(name="Promo Kitchen", owner=self.owner,
                                                    latitude="45.5", longitude="-73.5")
        self.item = MenuItem.objects.create(restaurant=self.restaurant, name="Meal", price="20.00")
        self.client = APIClient()
        self.client.force_authenticate(self.customer)
        self.payload = {"restaurant_id": self.restaurant.pk,
                        "items": [{"menu_item_id": self.item.pk, "quantity": 1}],
                        "promo_code": "WELCOME5"}
        self.token = signing.dumps({"customer_id": self.customer.pk, "address": "123 Test Street",
                                   "latitude": "45.5", "longitude": "-73.5"}, salt=SALT)
        clock = patch("promotions.services.timezone.now", return_value=datetime(2026, 11, 26, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        config = patch("pricing.services.load_pricing_config", return_value={
            "delivery_fee": "3.99", "service_fee": "1.50",
            "small_order_threshold": "15.00", "small_order_surcharge": "2.00"})
        config.start()
        self.addCleanup(config.stop)

    def quote(self, **changes):
        return self.client.post("/api/pricing/checkout/quote/", {**self.payload, **changes}, format="json")

    def place(self, **changes):
        return self.client.post("/api/orders/", {**self.payload, "delivery_address_token": self.token,
                                               **changes}, format="json")

    def test_exact_minimum_and_case_normalization(self):
        response = self.quote(promo_code="  welcome5  ")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["promo_code"], "WELCOME5")
        self.assertEqual(response.data["discount"], "5.00")
        self.assertEqual(response.data["total"], "20.49")
        self.assertFalse(Order.objects.exists())

    def test_invalid_codes_rejected_in_quote_and_placement(self):
        for code, reason in [("UNKNOWN", "does not exist"), ("EXPIRED5", "expired"),
                             ("FEAST10", "at least $40.00")]:
            for request in (self.quote, self.place):
                with self.subTest(code=code, endpoint=request.__name__):
                    response = request(promo_code=code)
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(reason, str(response.data))
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderLedger.objects.exists())

    def test_minimum_excludes_fees_and_cart_is_revalidated(self):
        self.assertEqual(self.quote().status_code, 200)
        self.item.price = Decimal("19.99")
        self.item.save()
        response = self.place()
        self.assertEqual(response.status_code, 400)
        self.assertIn("at least $20.00", str(response.data))
        self.assertFalse(Order.objects.exists())

    def test_expiry_between_preview_and_placement(self):
        self.assertEqual(self.quote().status_code, 200)
        with patch("promotions.services.timezone.now", return_value=datetime(2028, 1, 1, 5, tzinfo=timezone.utc)):
            response = self.place()
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", str(response.data))
        self.assertFalse(Order.objects.exists())

    def test_one_code_and_server_owned_discount(self):
        self.assertEqual(self.quote(promo_code=["WELCOME5", "FEAST10"]).status_code, 400)
        self.assertEqual(self.place(promo_code="WELCOME5,FEAST10").status_code, 400)
        response = self.place(discount="999.00", total="0.00")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["pricing"]["total"], "20.49")

    def test_no_promo_preserves_fees_and_surcharge(self):
        self.item.price = Decimal("12.00")
        self.item.save()
        response = self.quote(promo_code="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], "19.49")
        self.assertEqual(response.data["discount"], "0.00")

    def test_saved_price_survives_expiry_and_config_changes_and_limits_refunds(self):
        response = self.place()
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["id"])
        order.status = Order.Status.DELIVERED
        order.save()
        with patch("pricing.services.load_pricing_config", side_effect=AssertionError("Must use snapshot")), \
             patch("promotions.services.validate_promo_code", side_effect=AssertionError("Do not revalidate old orders")):
            self.assertEqual(calculate_order_pricing(order)["total"], Decimal("20.49"))
            ledger = record_order_ledger(order)
            self.assertEqual(record_order_ledger(order).pk, ledger.pk)
            summary = self.client.get(f"/api/pricing/orders/{order.pk}/summary/")
            self.assertEqual(summary.data["total"], "20.49")
            self.assertEqual(summary.data["discount"], "5.00")
        self.assertEqual(ledger.total_charge, Decimal("20.49"))
        self.assertEqual(ledger.promo_code, "WELCOME5")
        self.client.force_authenticate(self.operator)
        response = self.client.get("/api/pricing/ledger/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["discount"], "5.00")
        self.assertEqual(response.data[0]["total_charge"], "20.49")
        with self.assertRaises(ValidationError):
            submit_refund_request(self.customer, order.pk, "missing_items", requested_amount="25.49")
        refund = submit_refund_request(self.customer, order.pk, "missing_items", requested_amount="20.49")
        decide_refund_request(self.operator, refund.pk, "approve", approved_amount="20.49")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(ledger.refund_entries.get().amount, Decimal("20.49"))

    def test_quote_enforces_role_and_cart_rules(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.quote().status_code, 403)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.quote(items=[]).status_code, 400)
        self.assertEqual(self.quote(items=self.payload["items"] * 2).status_code, 400)
        self.item.status = MenuItem.Status.SOLD_OUT
        self.item.save()
        self.assertEqual(self.quote().status_code, 400)
        self.item.status = MenuItem.Status.AVAILABLE
        self.item.save()
        self.restaurant.status = Restaurant.Status.PAUSED
        self.restaurant.save()
        self.assertEqual(self.quote().status_code, 400)


    def test_percentage_discount_rounding_and_saved_charge(self):
        self.item.price = Decimal("20.05")
        self.item.save()
        response = self.quote(promo_code="save10")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["discount"], "2.01")
        self.assertEqual(response.data["total"], "23.53")
        placed = self.place(promo_code="SAVE10")
        self.assertEqual(placed.status_code, 201, placed.data)
        self.assertEqual(placed.data["pricing"], response.data)
        order = Order.objects.get(pk=placed.data["id"])
        order.status = Order.Status.DELIVERED
        order.save()
        ledger = record_order_ledger(order)
        self.assertEqual(ledger.discount, Decimal("2.01"))
        self.assertEqual(ledger.total_charge, Decimal("23.53"))

    def test_percentage_minimum_and_expiry_on_use(self):
        self.assertEqual(self.quote(promo_code="FEAST20").status_code, 400)
        items = [{"menu_item_id": self.item.pk, "quantity": 2}]
        response = self.quote(promo_code="FEAST20", items=items)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["discount"], "8.00")
        self.assertEqual(response.data["total"], "37.49")
        with patch("promotions.services.timezone.now", return_value=datetime(2028, 1, 1, 5, tzinfo=timezone.utc)):
            response = self.place(promo_code="FEAST20", items=items)
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", str(response.data))
        self.assertFalse(Order.objects.exists())


    def test_customer_order_cards_include_discounted_total_for_active_and_past_orders(self):
        response = self.place(promo_code="SAVE10")
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        for state in (Order.Status.PLACED, Order.Status.DELIVERED, Order.Status.REFUNDED):
            with self.subTest(state=state):
                order.status = state
                order.save()
                if state == Order.Status.DELIVERED:
                    record_order_ledger(order)
                response = self.client.get("/api/customer/orders/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data[0]["total"], "23.49")
                self.assertEqual(response.data[0]["promo_code"], "SAVE10")
                self.assertEqual(response.data[0]["discount"], "2.00")

    def test_customer_order_cards_use_original_ledger_for_legacy_orders(self):
        order = Order.objects.create(customer=self.customer, restaurant=self.restaurant,
                                     status=Order.Status.DELIVERED)
        OrderLine.objects.create(order=order, menu_item=self.item, quantity=1, unit_price="20.00")
        record_order_ledger(order)
        with patch("pricing.services.load_pricing_config", side_effect=AssertionError("Use original charge")):
            response = self.client.get("/api/customer/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["total"], "25.49")
        self.assertEqual(response.data[0]["promo_code"], "")
