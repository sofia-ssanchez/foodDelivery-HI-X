import json
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.utils import timezone
from .models import OrderLedger

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

FINAL_STATES = ["delivered", "rejected", "cancelled"]


def record_order_ledger(order):

    if order.status not in FINAL_STATES:
        raise ValueError("Order has not reached a final state")

    pricing = calculate_order_pricing(order)

    ledger_entry, created = OrderLedger.objects.get_or_create(
        order=order,
        defaults={
            "final_state": order.status,
            "order_created_at": order.created_at,
            "finalized_at": timezone.now(),
            "subtotal": pricing["subtotal"],
            "delivery_fee": pricing["delivery_fee"],
            "service_fee": pricing["service_fee"],
            "small_order_surcharge": pricing["small_order_surcharge"],
            "total_charge": pricing["total"]
        }
    )

    return ledger_entry