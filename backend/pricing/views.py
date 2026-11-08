
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from guards.permissions import RequireCustomer
from orders.models import Order
from .services import calculate_order_pricing


class OrderSummaryView(APIView):
    permission_classes = [RequireCustomer]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("restaurant").prefetch_related("lines__menu_item"),
            id=order_id,
            customer=request.user
        )

        if order.status != "delivered":
            return Response(
                {"detail": "Order summary is available after delivery."},
                status=status.HTTP_409_CONFLICT
            )

        pricing = calculate_order_pricing(order)

        items = [
            {
                "name": line.menu_item.name,
                "quantity": line.quantity,
                "unit_price": str(line.unit_price),
                "line_total": str(line.unit_price * line.quantity)
            }
            for line in order.lines.all()
        ]

        return Response({
            "order_id": order.id,
            "restaurant": order.restaurant.name,
            "status": order.status,
            "created_at": order.created_at,
            "items": items,
            "subtotal": str(pricing["subtotal"]),
            "delivery_fee": str(pricing["delivery_fee"]),
            "service_fee": str(pricing["service_fee"]),
            "small_order_surcharge": str(pricing["small_order_surcharge"]),
            "total": str(pricing["total"])
        })
