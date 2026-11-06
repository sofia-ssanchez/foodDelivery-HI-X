
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from guards.permissions import RequireCustomer
from orders.models import Order
from .services import calculate_order_pricing
from guards.permissions import RequireAuth
from .models import OrderLedger


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

class OperatorLedgerView(APIView):
    permission_classes = [RequireAuth]

    def get(self, request):
        if request.user.role != request.user.Role.OPERATOR:
            return Response(
                {"detail": "Only operators can access the order ledger."},
                status=status.HTTP_403_FORBIDDEN
            )

        entries = (
            OrderLedger.objects
            .select_related("order", "order__restaurant")
            .prefetch_related("order__lines__menu_item")
            .order_by("-finalized_at")
        )

        ledger = [
            {
                "order_id": entry.order_id,
                "restaurant": entry.order.restaurant.name,
                "final_state": entry.final_state,
                "order_created_at": entry.order_created_at,
                "finalized_at": entry.finalized_at,

                "items": [
                    {
                        "name": line.menu_item.name,
                        "quantity": line.quantity,
                        "unit_price": str(line.unit_price),
                        "line_total": str(line.unit_price * line.quantity),
                    }
                    for line in entry.order.lines.all()
                ],

                "subtotal": str(entry.subtotal),
                "delivery_fee": str(entry.delivery_fee),
                "service_fee": str(entry.service_fee),
                "small_order_surcharge": str(entry.small_order_surcharge),
                "total_charge": str(entry.total_charge),
            }
            for entry in entries
        ]

        return Response(ledger)