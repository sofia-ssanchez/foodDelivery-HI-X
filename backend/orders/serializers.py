from rest_framework import serializers
from .models import MenuItem, Restaurant

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
    restaurant_id = serializers.IntegerField(min_value=1)
    items = OrderItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        item_ids = [item["menu_item_id"] for item in items]

        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                "Duplicate menu items are not allowed."
            )

        return items
