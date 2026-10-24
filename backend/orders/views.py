from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from guards.permissions import RequireAuth, RequireRestaurantUser
from .models import MenuItem, Restaurant, Order
from .commands import PlaceOrderCommand
from .serializers import (MenuItemSerializer, PlaceOrderSerializer, RestaurantSerializer,
                          RestaurantOrderSerializer, OrderStatusSerializer)

class RestaurantListView(generics.ListAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [RequireAuth]


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


class RestaurantOrderBoardView(generics.GenericAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = RestaurantOrderSerializer

    def get(self, request):
        restaurants = Restaurant.objects.filter(owner=request.user).order_by("name", "id")
        orders = Order.objects.filter(restaurant__owner=request.user).select_related(
            "customer", "restaurant"
        ).prefetch_related("lines__menu_item").order_by("created_at", "id")
        return Response({
            "restaurants": RestaurantSerializer(restaurants, many=True).data,
            "orders": self.get_serializer(orders, many=True).data,
        })


class RestaurantOrderStatusView(generics.GenericAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = OrderStatusSerializer

    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk, restaurant__owner=request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected = serializer.validated_data["expected_status"]
        target = serializer.validated_data["status"]
        if order.status != expected:
            return Response({"detail": "This order has changed. Refresh the board and try again."}, status=409)
        try:
            order.transition(target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        # Atomic compare-and-update protects against stale tabs and duplicate clicks.
        updated = Order.objects.filter(pk=order.pk, restaurant__owner=request.user, status=expected).update(status=order.status)
        if not updated:
            return Response({"detail": "This order has changed. Refresh the board and try again."}, status=409)
        order.refresh_from_db()
        return Response(RestaurantOrderSerializer(order).data)
