"""Read-only data views for the customer, restaurant, and operator dashboards."""

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from guards.permissions import RequireAuth, RequireCustomer, RequireOperator, RequireRestaurantUser
from .models import MenuItem, Order, Restaurant
from .serializers import MenuItemSerializer, RestaurantOrderSerializer, RestaurantSerializer


class CustomerOrderListView(generics.ListAPIView):
    permission_classes = [RequireCustomer]
    serializer_class = RestaurantOrderSerializer
    pagination_class = None

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).select_related(
            "customer", "restaurant"
        ).prefetch_related("lines__menu_item").order_by("-created_at", "-id")



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



class OperatorOverviewView(APIView):
    permission_classes = [RequireOperator]

    def get(self, request):
        users = get_user_model().objects
        user_counts = dict(users.values("role").annotate(count=Count("id")).values_list("role", "count"))
        restaurant_counts = dict(Restaurant.objects.values("status").annotate(count=Count("id")).values_list("status", "count"))
        order_counts = dict(Order.objects.values("status").annotate(count=Count("id")).values_list("status", "count"))
        active_statuses = ["placed", "accepted", "preparing", "ready", "picked_up"]
        return Response({
            "total_users": sum(user_counts.values()),
            "active_users": users.filter(is_active=True).count(),
            "total_restaurants": sum(restaurant_counts.values()),
            "total_orders": sum(order_counts.values()),
            "active_orders": sum(order_counts.get(status, 0) for status in active_statuses),
            "users_by_role": user_counts,
            "restaurants_by_status": restaurant_counts,
            "orders_by_status": order_counts,
            "updated_at": timezone.now(),
        })

