"""Order creation and status-changing views."""

from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from delivery.models import Courier
from guards.permissions import RequireAuth, RequireCustomer, RequireOperator, RequireRestaurantUser
from .address_lookup import SALT, search_addresses
from .commands import (
    CustomerCancelOrderCommand,
    OperatorCancelOrderCommand,
    PlaceOrderCommand,
    RESTAURANT_ORDER_COMMANDS,
)
from .models import Order, OrderStatusEvent
from .serializers import (
    AddressQuerySerializer,
    LocationSerializer,
    OperatorCancelOrderSerializer,
    PlaceOrderSerializer,
    RestaurantOrderSerializer,
    OrderStatusSerializer,
)


class PlaceOrderView(generics.CreateAPIView):
    serializer_class = PlaceOrderSerializer
    permission_classes = [RequireAuth]

    def create(self, request, *args, **kwargs):
        if request.user.role != request.user.Role.CUSTOMER:
            raise PermissionDenied("Only customers can place orders.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        command = PlaceOrderCommand(
            customer=request.user,
            restaurant_id=serializer.validated_data["restaurant_id"],
            items=serializer.validated_data["items"],
            delivery_address_token=serializer.validated_data["delivery_address_token"],
            delivery_unit=serializer.validated_data.get("delivery_unit", ""),
        )

        order = command.execute()

        return Response(
            {
                "id": order.id,
                "restaurant_id": order.restaurant_id,
                "status": order.status,
            },
            status=status.HTTP_201_CREATED,
        )


class RestaurantOrderStatusView(generics.GenericAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = OrderStatusSerializer

    def patch(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        command_class = RESTAURANT_ORDER_COMMANDS[
            serializer.validated_data["status"]
        ]

        command = command_class(
            actor=request.user,
            order_id=pk,
            expected_status=serializer.validated_data["expected_status"],
        )

        order = command.execute()
        return Response(RestaurantOrderSerializer(order).data)


class OperatorOrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusEvent
        fields = [
            "event_id",
            "transition_number",
            "from_status",
            "to_status",
            "timestamp",
            "actor_username",
            "actor_role",
        ]


class OperatorOrderHistorySerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.username",
        read_only=True,
    )
    restaurant_name = serializers.CharField(
        source="restaurant.name",
        read_only=True,
    )
    events = OperatorOrderEventSerializer(
        source="status_events",
        many=True,
        read_only=True,
    )
    items = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "restaurant_name",
            "status",
            "created_at",
            "items",
            "events",
        ]

    def get_items(self, order):
        return [
            {
                "name": line.menu_item.name,
                "quantity": line.quantity,
                "unit_price": str(line.unit_price),
                "line_total": str(line.unit_price * line.quantity),
            }
            for line in order.lines.select_related("menu_item").all()
        ]


class OperatorOrderHistoryView(generics.ListAPIView):
    serializer_class = OperatorOrderHistorySerializer
    permission_classes = [RequireAuth]

    def get_queryset(self):
        if (
            not self.request.user.is_authenticated
            or self.request.user.role != self.request.user.Role.OPERATOR
        ):
            raise PermissionDenied(
                "Only operators can view order history."
            )

        return (
            Order.objects
            .select_related("customer", "restaurant")
            .prefetch_related("status_events", "lines__menu_item")
            .order_by("-created_at", "-id")
        )
class CustomerCancelOrderView(generics.GenericAPIView):
    permission_classes = [RequireCustomer]

    def post(self, request, pk):
        order = CustomerCancelOrderCommand(
            actor=request.user,
            order_id=pk,
            expected_status=Order.Status.PLACED,
        ).execute()
        return Response({"id": order.id, "status": order.status})


class OperatorCancelOrderView(generics.GenericAPIView):
    permission_classes = [RequireOperator]
    serializer_class = OperatorCancelOrderSerializer

    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = OperatorCancelOrderCommand(
            actor=request.user,
            order_id=pk,
            expected_status=serializer.validated_data["expected_status"],
        ).execute()
        return Response({"id": order.id, "status": order.status})



class AddressLookupView(APIView):
    permission_classes = [RequireCustomer]

    def post(self, request):
        serializer = AddressQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = search_addresses(serializer.validated_data["address"])
        response = Response({"results": [
            {"address": result["address"], "token": signing.dumps(
                {**result, "customer_id": request.user.id}, salt=SALT
            )} for result in results
        ]})
        response["Cache-Control"] = "no-store"
        return response


class MapLocationView(APIView):
    permission_classes = [RequireAuth]

    @transaction.atomic
    def patch(self, request):
        user = request.user
        if user.role != "courier":
            raise PermissionDenied("Only couriers can update their map position. Customers enter an address at checkout.")
        serializer = LocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        courier = get_object_or_404(Courier, user=user)
        Courier.objects.filter(pk=courier.pk).update(**serializer.validated_data)
        return Response({"detail": "Location saved."})


class DemoResetView(APIView):
    permission_classes = [RequireAuth]

    def post(self, request):
        from .demo import reset_demo
        response = Response(reset_demo())
        response['Cache-Control'] = 'no-store'
        return response
