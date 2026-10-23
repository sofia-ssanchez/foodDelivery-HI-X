from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from guards.permissions import RequireAuth
from .models import MenuItem, Order, Restaurant
from .commands import PlaceOrderCommand, UpdateOrderStatusCommand
from .serializers import MenuItemSerializer, PlaceOrderSerializer, RestaurantSerializer

class RestaurantListView(generics.ListAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [RequireAuth]


class UpdateOrderStateView(APIView):
    permission_classes = [RequireAuth]

    def patch(self, request, order_id):
        target_state = request.data.get("status")
        if not isinstance(target_state, str) or not target_state.strip():
            raise ValidationError({"status": "Provide the requested order status."})

        order = get_object_or_404(
            Order.objects.select_related("restaurant"), pk=order_id,
        )
        is_owner = (
            request.user.role == request.user.Role.RESTAURANT
            and order.restaurant.owner_id == request.user.pk
        )
        is_customer = (
            request.user.role == request.user.Role.CUSTOMER
            and order.customer_id == request.user.pk
        )
        if not (is_owner or (is_customer and target_state == "cancelled")):
            raise PermissionDenied("You cannot update this order's state.")

        # The command will validate the transition and persist the new status.
        command = UpdateOrderStatusCommand(
            order_id=order.pk,
            target_state=target_state,
        )
        try:
            order = command.execute()
        except ValueError as exc:
            raise ValidationError({"status": str(exc)}) from exc

        return Response({"id": order.pk, "status": order.status})


class RestaurantMenuView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [RequireAuth]

    def get_queryset(self):
        return MenuItem.objects.filter(
            restaurant_id=self.kwargs["restaurant_id"]
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


