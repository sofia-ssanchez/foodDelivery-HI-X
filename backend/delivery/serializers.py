from rest_framework import serializers

from .models import Courier, DeliveryAssignment
from orders.serializers import RestaurantOrderLineSerializer


class DutySerializer(serializers.Serializer):
    on_duty = serializers.BooleanField()


class ReassignDeliverySerializer(serializers.Serializer):
    courier_id = serializers.IntegerField(min_value=1)


class CourierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courier
        fields = ["id", "status", "latitude", "longitude"]
        read_only_fields = fields


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    delivery_address = serializers.CharField(source="order.delivery_address", read_only=True)
    delivery_unit = serializers.CharField(source="order.delivery_unit", read_only=True)
    customer_name = serializers.CharField(source="order.customer.username", read_only=True)
    created_at = serializers.DateTimeField(source="order.created_at", read_only=True)
    lines = RestaurantOrderLineSerializer(source="order.lines", many=True, read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    restaurant_name = serializers.CharField(source="order.restaurant.name", read_only=True)
    restaurant_latitude = serializers.DecimalField(
        source="order.restaurant.latitude", max_digits=9, decimal_places=6, read_only=True
    )
    restaurant_longitude = serializers.DecimalField(
        source="order.restaurant.longitude", max_digits=9, decimal_places=6, read_only=True
    )

    class Meta:
        model = DeliveryAssignment
        fields = [
            "id", "order_id", "delivery_address", "delivery_unit", "customer_name", "created_at", "lines", "status", "order_status", "restaurant_name",
            "restaurant_latitude", "restaurant_longitude", "offered_at",
            "expired_at", "accepted_at", "declined_at", "cancelled_at", "picked_up_at",
            "delivered_at",
        ]
        read_only_fields = fields
