from rest_framework import serializers
from .commands import RESTAURANT_ORDER_COMMANDS
from decimal import Decimal
from .models import MenuItem, Restaurant, Order, OrderLine

class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = [
            "id",
            "name",
            "status",
            "latitude",
            "longitude",
        ]
        read_only_fields = fields

class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = [
            "id",
            "restaurant",
            "name",
            "price",
            "status",
        ]
        read_only_fields = fields

class OrderItemInputSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class PlaceOrderSerializer(serializers.Serializer):
    delivery_address_token = serializers.CharField(max_length=3000)
    delivery_unit = serializers.CharField(max_length=80, required=False, allow_blank=True)
    restaurant_id = serializers.IntegerField(min_value=1)
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        item_ids = [item["menu_item_id"] for item in items]

        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                "Duplicate menu items are not allowed."
            )

        return items


class RestaurantOrderLineSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="menu_item.name", read_only=True)

    class Meta:
        model = OrderLine
        fields = ["id", "name", "quantity", "unit_price"]


class RestaurantOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.username", read_only=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    lines = RestaurantOrderLineSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    def get_total(self, order):
        return str(sum((line.unit_price * line.quantity for line in order.lines.all()), Decimal("0.00")))

    class Meta:
        model = Order
        fields = ["id", "restaurant_id", "restaurant_name", "customer_name", "status", "created_at", "picked_up_at", "delivered_at", "lines", "total"]


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=list(RESTAURANT_ORDER_COMMANDS))
    expected_status = serializers.ChoiceField(choices=Order.Status.choices)


class OperatorCancelOrderSerializer(serializers.Serializer):
    expected_status = serializers.ChoiceField(
        choices=(
            Order.Status.ACCEPTED,
            Order.Status.PREPARING,
            Order.Status.READY,
        )
    )


class AddressQuerySerializer(serializers.Serializer):
    address = serializers.CharField(min_length=5, max_length=250)


class LocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)
