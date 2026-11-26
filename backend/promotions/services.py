"""Predefined promotions: no user-facing creation or editing operations."""
import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError


def validate_promo_code(code, subtotal):
    """Validate at use time; minimum spend excludes fees and discounts."""
    code = code.strip().upper()
    if not code:
        return "", Decimal("0.00")
    with open(settings.BASE_DIR / "config" / "promotions.json") as file:
        promotion = json.load(file).get(code)
    if promotion is None:
        raise ValidationError({"detail": "Promo code does not exist."})
    if timezone.now() >= datetime.fromisoformat(promotion["expires_at"]):
        raise ValidationError({"detail": f"Promo code {code} has expired."})
    minimum = Decimal(promotion["minimum_spend"])
    if subtotal < minimum:
        raise ValidationError({"detail": f"Promo code {code} requires at least ${minimum:.2f} in items before fees."})
    discount = Decimal(promotion["discount"])
    if promotion.get("type", "fixed") == "percentage":
        discount = subtotal * discount / Decimal("100")
    # The shared pricing service rounds the resulting discount to cents.
    return code, min(discount, subtotal)
