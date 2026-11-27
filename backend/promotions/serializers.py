from rest_framework import serializers

from orders.models import Restaurant
from .models import Promotion


class PromotionSerializer(serializers.ModelSerializer):
    restaurant_id = serializers.IntegerField(required=False)

    class Meta:
        model = Promotion
        fields = ["id", "restaurant_id", "code", "discount_type", "discount", "minimum_order", "expires_at", "is_active"]

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter a promo code.")
        return value

    def validate(self, attrs):
        restaurant_id = attrs.get("restaurant_id")
        request = self.context["request"]
        if restaurant_id is not None and not Restaurant.objects.filter(pk=restaurant_id, owner=request.user).exists():
            raise serializers.ValidationError({"restaurant_id": "Choose one of your restaurants."})
        if self.instance is not None and restaurant_id is not None and restaurant_id != self.instance.restaurant_id:
            raise serializers.ValidationError({"restaurant_id": "A promo code cannot be moved to another restaurant."})
        if self.instance is None and restaurant_id is None:
            raise serializers.ValidationError({"restaurant_id": "Choose a restaurant."})
        discount = attrs.get("discount", getattr(self.instance, "discount", None))
        minimum_order = attrs.get("minimum_order", getattr(self.instance, "minimum_order", None))
        if discount is not None and discount <= 0:
            raise serializers.ValidationError({"discount": "Discount must be greater than zero."})
        if minimum_order is not None and minimum_order < 0:
            raise serializers.ValidationError({"minimum_order": "Minimum order cannot be negative."})
        if attrs.get("discount_type", getattr(self.instance, "discount_type", None)) == Promotion.DiscountType.PERCENTAGE:
            discount = attrs.get("discount", getattr(self.instance, "discount", None))
            if discount is not None and discount > 100:
                raise serializers.ValidationError({"discount": "Percentage discounts cannot exceed 100%."})
        code = attrs.get("code")
        target_restaurant_id = restaurant_id or getattr(self.instance, "restaurant_id", None)
        if code is not None and target_restaurant_id is not None:
            duplicate = Promotion.objects.filter(restaurant_id=target_restaurant_id, code=code)
            if self.instance is not None:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError({"code": "This restaurant already uses that promo code."})
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("restaurant_id", None)
        return super().update(instance, validated_data)
