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
from orders.serializers import CheckoutQuoteSerializer
from orders.checkout import get_restaurant, prepare_checkout_lines
from .services import calculate_line_pricing


class OrderSummaryView(APIView):
    permission_classes = [RequireCustomer]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("restaurant").prefetch_related("lines__menu_item"),
            id=order_id,
            customer=request.user
        )

        if not self._is_summary_available(order):
            return Response(
                {"detail": "Order summary is available after delivery."},
                status=status.HTTP_409_CONFLICT
            )

        pricing = calculate_order_pricing(order)

        items = self._build_items(order)

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
            "promo_code": pricing["promo_code"],
            "discount": str(pricing["discount"]),
            "total": str(pricing["total"])
        })

    def _is_summary_available(self, order):
        return order.status in [
            Order.Status.DELIVERED,
            Order.Status.PARTIALLY_REFUNDED,
            Order.Status.REFUNDED,
        ]

    def _build_items(self, order):
        return [
            {
                "name": line.menu_item.name,
                "quantity": line.quantity,
                "unit_price": str(line.unit_price),
                "line_total": str(line.unit_price * line.quantity)
            }
            for line in order.lines.all()
        ]


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

        ledger = [
            self._serialize_ledger_entry(entry)
            for entry in entries
        ]

        return Response(ledger)

    def _serialize_refunds(self, entry):
        return [
            {
                "refund_id": refund.id,
                "refund_request_id": refund.refund_request_id,
                "amount": str(refund.amount),
                "created_at": refund.created_at,
                "operator": refund.operator.username,
            }
            for refund in entry.refund_entries.all().order_by("created_at")
        ]

    def _serialize_items(self, entry):
        return [
            {
                "name": line.menu_item.name,
                "quantity": line.quantity,
                "unit_price": str(line.unit_price),
                "line_total": str(line.unit_price * line.quantity),
            }
            for line in entry.order.lines.all()
        ]

    def _serialize_ledger_entry(self, entry):
        total_refunded = get_total_refunded(entry)
        net_charge = money(entry.total_charge - total_refunded)

        return {
            "order_id": entry.order_id,
            "restaurant": entry.order.restaurant.name,
            "final_state": entry.final_state,
            "current_order_status": entry.order.status,
            "order_created_at": entry.order_created_at,
            "finalized_at": entry.finalized_at,

            "items": self._serialize_items(entry),

            "subtotal": str(entry.subtotal),
            "delivery_fee": str(entry.delivery_fee),
            "service_fee": str(entry.service_fee),
            "small_order_surcharge": str(
                entry.small_order_surcharge
            ),

            # Original charge is never modified.
            "total_charge": str(entry.total_charge),
            "promo_code": entry.promo_code,
            "discount": str(entry.discount),

            # Separate refund transactions.
            "refunds": self._serialize_refunds(entry),
            "total_refunded": str(total_refunded),
            "net_charge": str(net_charge),
        }


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

    def get(self, request):
        refunds = RefundRequest.objects.filter(
            customer=request.user
        ).select_related("order").order_by("-created_at")

        data = [
            {
                "id": refund.id,
                "order_id": refund.order_id,
                "reason": refund.reason,
                "reason_display": refund.get_reason_display(),
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
                "decision_notes": refund.decision_notes,
                "created_at": refund.created_at,
                "decided_at": refund.decided_at,
            }
            for refund in refunds
        ]

        return Response(data, status=status.HTTP_200_OK)


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


class CheckoutQuoteView(APIView):
    permission_classes = [RequireCustomer]

    def post(self, request):
        serializer = CheckoutQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        restaurant = get_restaurant(data["restaurant_id"])
        lines = prepare_checkout_lines(restaurant, data["items"])
        pricing = calculate_line_pricing(lines, data["promo_code"], restaurant_id=restaurant.pk)
        return Response({key: str(value) for key, value in pricing.items()})
