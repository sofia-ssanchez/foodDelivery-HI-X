"""Restaurant-owned promotions plus the original demo-wide promo codes."""
import json
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Promotion


def validate_promo_code(code, subtotal, restaurant_id=None):
    """Validate at use time; minimum spend excludes fees and discounts."""
    code = code.strip().upper()
    if not code:
        return "", Decimal("0.00")
    if restaurant_id is not None:
        promotion = Promotion.objects.filter(code=code, restaurant_id=restaurant_id, is_active=True).first()
        if promotion is not None:
            if timezone.now() >= promotion.expires_at:
                raise ValidationError({"detail": f"Promo code {code} has expired."})
            if subtotal < promotion.minimum_order:
                raise ValidationError({"detail": f"Promo code {code} requires at least ${promotion.minimum_order:.2f} in items before fees."})
            discount = promotion.discount
            if promotion.discount_type == Promotion.DiscountType.PERCENTAGE:
                discount = subtotal * discount / Decimal("100")
            return code, min(discount, subtotal)
        if Promotion.objects.filter(code=code).exists():
            raise ValidationError({"detail": "Promo code is not available at this restaurant."})
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
