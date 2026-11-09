"""Order creation and status-changing views."""

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from guards.permissions import RequireAuth, RequireCustomer, RequireOperator, RequireRestaurantUser
from .commands import (
    CustomerCancelOrderCommand,
    OperatorCancelOrderCommand,
    PlaceOrderCommand,
    RESTAURANT_ORDER_COMMANDS,
)
from .models import Order
from .serializers import (
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
        command_class = RESTAURANT_ORDER_COMMANDS[serializer.validated_data["status"]]
        command = command_class(
            actor=request.user,
            order_id=pk,
            expected_status=serializer.validated_data["expected_status"],
        )
        order = command.execute()
        return Response(RestaurantOrderSerializer(order).data)


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

