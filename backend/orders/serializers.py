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
