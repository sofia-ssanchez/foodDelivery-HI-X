from rest_framework import serializers

from .models import Courier, DeliveryAssignment


class DutySerializer(serializers.Serializer):
    on_duty = serializers.BooleanField()


class CourierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courier
        fields = ["id", "status", "latitude", "longitude"]
        read_only_fields = fields


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
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
            "id", "order_id", "status", "order_status", "restaurant_name",
            "restaurant_latitude", "restaurant_longitude", "offered_at",
            "accepted_at", "declined_at", "cancelled_at", "picked_up_at",
            "delivered_at",
        ]
        read_only_fields = fields
