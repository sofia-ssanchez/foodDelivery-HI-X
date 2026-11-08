import json
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def load_pricing_config():
    path = settings.BASE_DIR / "config" / "pricing.json"

    with open(path, "r") as file:
        return json.load(file)


def calculate_order_pricing(order):
    config = load_pricing_config()

    subtotal = Decimal("0.00")

    for line in order.lines.all():
        if line.quantity <= 0 or line.unit_price < 0:
            raise ValueError("Invalid order line")

        subtotal += line.unit_price * line.quantity

    subtotal = money(subtotal)

    delivery_fee = money(config["delivery_fee"])
    service_fee = money(config["service_fee"])
    threshold = money(config["small_order_threshold"])

    surcharge = Decimal("0.00")

    if subtotal < threshold:
        surcharge = money(config["small_order_surcharge"])

    total = money(subtotal + delivery_fee + service_fee + surcharge)

    return {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "service_fee": service_fee,
        "small_order_surcharge": surcharge,
        "total": total
    }
