##tests that our calculations are correct
## Total = Subtotal + Delivery Fee + Service Fee + Surcharge


from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from .services import calculate_order_pricing


class PricingTests(SimpleTestCase):

    def calculate(self, items):
        lines = [
            SimpleNamespace(quantity=quantity, unit_price=Decimal(price))
            for quantity, price in items
        ]

        order = SimpleNamespace(
            lines=SimpleNamespace(all=lambda: lines)
        )

        config = {
            "delivery_fee": "3.99",
            "service_fee": "1.50",
            "small_order_threshold": "15.00",
            "small_order_surcharge": "2.00"
        }

        with patch("pricing.services.load_pricing_config", return_value=config):
            return calculate_order_pricing(order)

    def test_regular_order(self):
        result = self.calculate([(2, "12.00")])

        self.assertEqual(result["subtotal"], Decimal("24.00"))
        self.assertEqual(result["total"], Decimal("29.49"))

    def test_small_order(self):
        result = self.calculate([(1, "10.00")])

        self.assertEqual(result["small_order_surcharge"], Decimal("2.00"))
        self.assertEqual(result["total"], Decimal("17.49"))

    def test_order_at_threshold(self):
        result = self.calculate([(1, "15.00")])

        self.assertEqual(result["small_order_surcharge"], Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("20.49"))

    def test_multiple_items(self):
        result = self.calculate([(2, "8.00"), (1, "5.00")])

        self.assertEqual(result["subtotal"], Decimal("21.00"))
        self.assertEqual(result["total"], Decimal("26.49"))

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            self.calculate([(0, "12.00")])

    def test_deterministic_pricing(self):
        items = [(2, "12.00"), (1, "5.00")]

        self.assertEqual(self.calculate(items), self.calculate(items))
