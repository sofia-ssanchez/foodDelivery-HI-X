from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class SignupSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(required=False, max_length=150)
    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "role",
            "restaurant_name",
        ]

    def validate(self, attrs):
        if attrs.get("role") == User.Role.RESTAURANT:
            restaurant_name = attrs.get("restaurant_name", "").strip()
            if not restaurant_name:
                raise serializers.ValidationError({"restaurant_name": "Enter your restaurant name."})
            attrs["restaurant_name"] = restaurant_name
        else:
            attrs.pop("restaurant_name", None)
        return attrs
        
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        restaurant_name = validated_data.pop("restaurant_name", None)

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        if user.role == User.Role.RESTAURANT:
            from orders.models import Restaurant

            Restaurant.objects.create(
                name=restaurant_name,
                owner=user,
                latitude="45.501700",
                longitude="-73.567300",
            )

        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username

        return token
