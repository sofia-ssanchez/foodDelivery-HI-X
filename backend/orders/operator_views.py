from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from guards.permissions import RequireOperator
from .models import Order, Restaurant


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
