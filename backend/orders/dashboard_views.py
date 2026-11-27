"""Read-only data views for the customer, restaurant, and operator dashboards."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from delivery.models import Courier, DeliveryAssignment

from guards.permissions import RequireAuth, RequireCustomer, RequireOperator, RequireRestaurantUser
from .commands import CreateMenuItemCommand, UpdateMenuItemCommand
from .address_lookup import read_restaurant_address
from .models import MenuItem, Order, Restaurant
from .serializers import (
    CustomerOrderSerializer,
    MenuItemSerializer,
    MenuItemWriteSerializer,
    RestaurantOrderSerializer,
    RestaurantCreateSerializer,
    RestaurantDetailsUpdateSerializer,
    RestaurantSerializer,
)


class CustomerOrderListView(generics.ListAPIView):
    permission_classes = [RequireCustomer]
    serializer_class = CustomerOrderSerializer
    pagination_class = None

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).select_related(
            "customer", "restaurant", "ledger_entry"
        ).prefetch_related("lines__menu_item").order_by("-created_at", "-id")



class RestaurantListView(generics.ListCreateAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [RequireAuth]

    def get_permissions(self):
        if self.request.method == "POST":
            return [RequireRestaurantUser()]
        return [RequireAuth()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RestaurantCreateSerializer
        return RestaurantSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = read_restaurant_address(serializer.validated_data["address_token"])
        restaurant = Restaurant.objects.create(
            name=serializer.validated_data["name"],
            address=location["address"],
            details_locked=True,
            owner=request.user,
            latitude=location["latitude"],
            longitude=location["longitude"],
        )
        return Response(
            RestaurantSerializer(restaurant).data,
            status=status.HTTP_201_CREATED,
        )



class RestaurantMenuView(generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [RequireAuth]

    def get_permissions(self):
        permission_class = (
            RequireRestaurantUser
            if self.request.method == "POST"
            else RequireAuth
        )
        return [permission_class()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MenuItemWriteSerializer
        return MenuItemSerializer

    def get_queryset(self):
        queryset = MenuItem.objects.filter(
            restaurant_id=self.kwargs["restaurant_id"]
        )
        if self.request.user.role == self.request.user.Role.RESTAURANT:
            queryset = queryset.filter(restaurant__owner=self.request.user)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = CreateMenuItemCommand(
            actor=request.user,
            restaurant_id=self.kwargs["restaurant_id"],
            **serializer.validated_data,
        ).execute()
        return Response(
            MenuItemSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class RestaurantMenuItemView(generics.GenericAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = MenuItemWriteSerializer

    def patch(self, request, restaurant_id, menu_item_id):
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response(
                {"detail": "At least one menu item field must be provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item = UpdateMenuItemCommand(
            actor=request.user,
            restaurant_id=restaurant_id,
            menu_item_id=menu_item_id,
            changes=serializer.validated_data,
        ).execute()
        return Response(MenuItemSerializer(item).data)


class RestaurantPauseActivityView(generics.GenericAPIView):
    serializer_class = RestaurantSerializer
    permission_classes = [RequireRestaurantUser]

    def get_queryset(self):
        return Restaurant.objects.filter(owner=self.request.user)

    def post(self, request, *args, **kwargs):
        restaurant = self.get_object()

        if restaurant.status == Restaurant.Status.OPEN:
            restaurant.status = Restaurant.Status.PAUSED

        elif restaurant.status == Restaurant.Status.PAUSED:
            restaurant.status = Restaurant.Status.OPEN

        restaurant.save(update_fields=["status"])
        return Response(self.get_serializer(restaurant).data)


class RestaurantAddressView(APIView):
    permission_classes = [RequireRestaurantUser]

    @transaction.atomic
    def post(self, request, restaurant_id):
        restaurant = get_object_or_404(Restaurant.objects.select_for_update(), pk=restaurant_id, owner=request.user)
        if restaurant.details_locked:
            return Response({"detail": "Restaurant name and address are locked."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RestaurantDetailsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address_token = serializer.validated_data.get("address_token", "")
        if address_token:
            location = read_restaurant_address(address_token)
            restaurant.address = location["address"]
            restaurant.latitude = location["latitude"]
            restaurant.longitude = location["longitude"]
        elif not restaurant.address:
            return Response({"detail": "Find and select a restaurant address."}, status=status.HTTP_400_BAD_REQUEST)
        restaurant.name = serializer.validated_data["name"]
        restaurant.details_locked = True
        restaurant.save(update_fields=["name", "address", "latitude", "longitude", "details_locked"])
        return Response(RestaurantSerializer(restaurant).data)


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


class OperatorRestaurantActivityView(APIView):
    permission_classes = [RequireOperator]

    @transaction.atomic
    def post(self, request, pk):
        restaurant = get_object_or_404(Restaurant.objects.select_for_update(), pk=pk)
        if restaurant.status == Restaurant.Status.OPEN:
            restaurant.status = Restaurant.Status.PAUSED
        else:
            restaurant.status = Restaurant.Status.OPEN
        restaurant.save(update_fields=["status"])
        return Response(RestaurantSerializer(restaurant).data)


class OperatorOperationsView(APIView):
    permission_classes = [RequireOperator]

    def get(self, request):
        restaurants = Restaurant.objects.order_by("name", "id")
        available_couriers = Courier.objects.select_related("user").filter(
            status=Courier.Status.IDLE,
            user__is_active=True,
            user__role="courier",
        ).exclude(
            assignments__status__in=(DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED)
        ).order_by("user__username")
        assignments = DeliveryAssignment.objects.filter(
            status=DeliveryAssignment.Status.ACCEPTED,
            picked_up_at__isnull=True,
            order__status=Order.Status.READY,
            courier__status=Courier.Status.OFFLINE,
        ).select_related("order__restaurant", "order__customer", "courier__user").prefetch_related("order__lines__menu_item").order_by("order__created_at", "order_id")
        return Response({
            "restaurants": RestaurantSerializer(restaurants, many=True).data,
            "available_couriers": [{"id": courier.pk, "username": courier.user.username} for courier in available_couriers],
            "offline_assignments": [{
                "assignment_id": assignment.pk,
                "order_id": assignment.order_id,
                "restaurant_name": assignment.order.restaurant.name,
                "customer_name": assignment.order.customer.username,
                "courier_name": assignment.courier.user.username,
                "created_at": assignment.order.created_at,
                "items": [{"name": line.menu_item.name, "quantity": line.quantity} for line in assignment.order.lines.all()],
            } for assignment in assignments],
        })

