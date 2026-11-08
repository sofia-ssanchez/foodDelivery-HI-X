from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from guards.permissions import RequireAuth, RequireCustomer
from orders.models import Order

from .models import OrderLedger, RefundRequest
from .serializers import (
    RefundRequestCreateSerializer,
    RefundDecisionSerializer,
)
from .services import (
    calculate_order_pricing,
    submit_refund_request,
    decide_refund_request,
    get_total_refunded,
    evaluate_refund_eligibility,
    money,
)


class OrderSummaryView(APIView):
    permission_classes = [RequireCustomer]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("restaurant").prefetch_related("lines__menu_item"),
            id=order_id,
            customer=request.user
        )

        if order.status not in [
            Order.Status.DELIVERED,
            Order.Status.PARTIALLY_REFUNDED,
            Order.Status.REFUNDED,
        ]:
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
        if (
            not request.user.is_active
            or request.user.role != request.user.Role.OPERATOR
        ):
            raise PermissionDenied(
                "Only operators can access the order ledger."
            )

        entries = (
            OrderLedger.objects
            .select_related("order", "order__restaurant")
            .prefetch_related(
                "order__lines__menu_item",
                "refund_entries__operator",
                "refund_entries__refund_request",
            )
            .order_by("-finalized_at")
        )

        ledger = []

        for entry in entries:
            refunds = [
                {
                    "refund_id": refund.id,
                    "refund_request_id": refund.refund_request_id,
                    "amount": str(refund.amount),
                    "created_at": refund.created_at,
                    "operator": refund.operator.username,
                }
                for refund in entry.refund_entries.all().order_by("created_at")
            ]

            total_refunded = get_total_refunded(entry)
            net_charge = money(entry.total_charge - total_refunded)

            ledger.append({
                "order_id": entry.order_id,
                "restaurant": entry.order.restaurant.name,
                "final_state": entry.final_state,
                "current_order_status": entry.order.status,
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
                "small_order_surcharge": str(
                    entry.small_order_surcharge
                ),

                # Original charge is never modified.
                "total_charge": str(entry.total_charge),

                # Separate refund transactions.
                "refunds": refunds,
                "total_refunded": str(total_refunded),
                "net_charge": str(net_charge),
            })

        return Response(ledger)

class CustomerRefundRequestView(APIView):
    permission_classes = [RequireCustomer]

    def post(self, request):
        serializer = RefundRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        refund_request = submit_refund_request(
            customer=request.user,
            order_id=data["order_id"],
            reason=data["reason"],
            details=data.get("details", ""),
            requested_amount=data.get("requested_amount"),
        )

        return Response(
            {
                "id": refund_request.id,
                "order_id": refund_request.order_id,
                "status": refund_request.status,
                "reason": refund_request.reason,
                "requested_amount": (
                    str(refund_request.requested_amount)
                    if refund_request.requested_amount is not None
                    else None
                ),
                "created_at": refund_request.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class OperatorRefundRequestListView(APIView):
    permission_classes = [RequireAuth]

    def get(self, request):
        if (
            not request.user.is_active
            or request.user.role != request.user.Role.OPERATOR
        ):
            raise PermissionDenied(
                "Only operators can view refund requests."
            )

        requests = (
            RefundRequest.objects
            .select_related("order", "customer", "order__restaurant")
            .order_by("-created_at")
        )

        data = [
            {
                "id": refund.id,
                "order_id": refund.order_id,
                "customer": refund.customer.username,
                "restaurant": refund.order.restaurant.name,
                "order_status": refund.order.status,
                "reason": refund.get_reason_display(),
                "reason_code": refund.reason,
                "details": refund.details,
                "requested_amount": (
                    str(refund.requested_amount)
                    if refund.requested_amount is not None
                    else None
                ),
                "status": refund.status,
                "approved_amount": (
                    str(refund.approved_amount)
                    if refund.approved_amount is not None
                    else None
                ),
                "eligibility": evaluate_refund_eligibility(refund),
                "decision_notes": refund.decision_notes,
                "created_at": refund.created_at,
                "decided_at": refund.decided_at,
                "operator": (
                    refund.operator.username
                    if refund.operator
                    else None
                ),
            }
            for refund in requests
        ]

        return Response(data)


class OperatorRefundDecisionView(APIView):
    permission_classes = [RequireAuth]

    def patch(self, request, refund_id):
        if (
            not request.user.is_active
            or request.user.role != request.user.Role.OPERATOR
        ):
            raise PermissionDenied(
                "Only operators can decide refund requests."
            )

        serializer = RefundDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        refund_request = decide_refund_request(
            operator=request.user,
            refund_request_id=refund_id,
            decision=data["decision"],
            approved_amount=data.get("approved_amount"),
            decision_notes=data.get("decision_notes", ""),
        )

        return Response({
            "id": refund_request.id,
            "order_id": refund_request.order_id,
            "status": refund_request.status,
            "approved_amount": (
                str(refund_request.approved_amount)
                if refund_request.approved_amount is not None
                else None
            ),
            "decision_notes": refund_request.decision_notes,
            "decided_at": refund_request.decided_at,
        })