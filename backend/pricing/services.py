import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.db import models, transaction
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import ValidationError, PermissionDenied

from orders.models import Order
from orders.event_services import record_order_status_event

from .models import OrderLedger, RefundRequest, RefundLedgerEntry


def money(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def load_pricing_config():
    path = settings.BASE_DIR / "config" / "pricing.json"

    with open(path, "r") as file:
        return json.load(file)


def calculate_order_pricing(order):
    config = load_pricing_config()

    subtotal = Decimal("0.00")

    for line in order.lines.all():
        if line.quantity <= 0 or line.unit_price < 0:
            raise ValueError("Invalid order line")

        subtotal += line.unit_price * line.quantity

    subtotal = money(subtotal)

    delivery_fee = money(config["delivery_fee"])
    service_fee = money(config["service_fee"])
    threshold = money(config["small_order_threshold"])

    surcharge = Decimal("0.00")

    if subtotal < threshold:
        surcharge = money(config["small_order_surcharge"])

    total = money(
        subtotal + delivery_fee + service_fee + surcharge
    )

    return {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "service_fee": service_fee,
        "small_order_surcharge": surcharge,
        "total": total,
    }


FINAL_STATES = ["delivered", "rejected", "cancelled"]


def record_order_ledger(order):
    if order.status not in FINAL_STATES:
        raise ValueError("Order has not reached a final state")

    pricing = calculate_order_pricing(order)

    ledger_entry, created = OrderLedger.objects.get_or_create(
        order=order,
        defaults={
            "final_state": order.status,
            "order_created_at": order.created_at,
            "finalized_at": timezone.now(),
            "subtotal": pricing["subtotal"],
            "delivery_fee": pricing["delivery_fee"],
            "service_fee": pricing["service_fee"],
            "small_order_surcharge": pricing["small_order_surcharge"],
            "total_charge": pricing["total"],
        },
    )

    return ledger_entry


def get_total_refunded(ledger_entry):
    total = ledger_entry.refund_entries.aggregate(
        total=models.Sum("amount")
    )["total"]

    return money(total or Decimal("0.00"))


@transaction.atomic
def submit_refund_request(
    customer,
    order_id,
    reason,
    details="",
    requested_amount=None,
):
    if (
        not customer.is_active
        or customer.role != customer.Role.CUSTOMER
    ):
        raise PermissionDenied(
            "Only customers can request refunds."
        )

    order = get_object_or_404(
        Order.objects.select_for_update(),
        pk=order_id,
        customer=customer,
    )

    if order.status not in [
        Order.Status.DELIVERED,
        Order.Status.REJECTED,
        Order.Status.CANCELLED,
        Order.Status.PARTIALLY_REFUNDED,
    ]:
        raise ValidationError(
            "Refunds can only be requested for finalized orders."
        )

    try:
        ledger_entry = OrderLedger.objects.get(order=order)
    except OrderLedger.DoesNotExist:
        raise ValidationError(
            "There is no ledger entry for this order."
        )

    total_refunded = get_total_refunded(ledger_entry)
    remaining_amount = money(
        ledger_entry.total_charge - total_refunded
    )

    if remaining_amount <= 0:
        raise ValidationError(
            "This order has already been fully refunded."
        )

    if requested_amount is not None:
        requested_amount = money(requested_amount)

        if requested_amount <= 0:
            raise ValidationError(
                "Requested amount must be greater than zero."
            )

        if requested_amount > remaining_amount:
            raise ValidationError(
                "Requested amount exceeds the remaining refundable balance."
            )

    if RefundRequest.objects.filter(
        order=order,
        status=RefundRequest.Status.PENDING,
    ).exists():
        raise ValidationError(
            "This order already has a pending refund request."
        )

    return RefundRequest.objects.create(
        order=order,
        customer=customer,
        reason=reason,
        details=details,
        requested_amount=requested_amount,
    )


@transaction.atomic
def decide_refund_request(
    operator,
    refund_request_id,
    decision,
    approved_amount=None,
    decision_notes="",
):
    if (
        not operator.is_active
        or operator.role != operator.Role.OPERATOR
    ):
        raise PermissionDenied(
            "Only operators can decide refund requests."
        )

    try:
        refund_request = (
            RefundRequest.objects
            .select_for_update()
            .select_related("order")
            .get(pk=refund_request_id)
        )
    except RefundRequest.DoesNotExist:
        raise ValidationError(
            "Refund request does not exist."
        )

    if refund_request.status != RefundRequest.Status.PENDING:
        raise ValidationError(
            "This refund request has already been decided."
        )

    if decision not in ["approve", "reject"]:
        raise ValidationError(
            "Decision must be approve or reject."
        )

    if decision == "reject":
        if not decision_notes.strip():
            raise ValidationError(
                "A reason is required when rejecting a refund."
            )

        refund_request.status = RefundRequest.Status.REJECTED
        refund_request.operator = operator
        refund_request.decision_notes = decision_notes
        refund_request.decided_at = timezone.now()

        refund_request.save(
            update_fields=[
                "status",
                "operator",
                "decision_notes",
                "decided_at",
            ]
        )

        return refund_request

    # Evaluate eligibility before allowing approval.
    eligibility = evaluate_refund_eligibility(refund_request)

    if eligibility["eligibility_status"] == "ineligible":
        raise ValidationError({
            "eligibility": eligibility,
            "detail": "This refund request is not eligible for approval.",
        })

    if eligibility["eligibility_status"] == "manual_review":
        if not decision_notes.strip():
            raise ValidationError(
                "An explanation is required to approve a request "
                "that requires manual review."
            )

    if approved_amount is None:
        raise ValidationError(
            "An approved amount is required."
        )

    approved_amount = money(approved_amount)

    if approved_amount <= 0:
        raise ValidationError(
            "Approved amount must be greater than zero."
        )

    ledger_entry = (
        OrderLedger.objects
        .select_for_update()
        .get(order=refund_request.order)
    )

    total_refunded = get_total_refunded(ledger_entry)
    remaining_amount = money(
        ledger_entry.total_charge - total_refunded
    )

    if approved_amount > remaining_amount:
        raise ValidationError(
            "Approved amount exceeds the remaining refundable balance."
        )

    if (
        refund_request.requested_amount is not None
        and approved_amount > refund_request.requested_amount
    ):
        raise ValidationError(
            "Approved amount cannot exceed the customer's requested amount."
        )

    refund_request.status = RefundRequest.Status.APPROVED
    refund_request.approved_amount = approved_amount
    refund_request.operator = operator
    refund_request.decision_notes = decision_notes
    refund_request.decided_at = timezone.now()

    refund_request.save(
        update_fields=[
            "status",
            "approved_amount",
            "operator",
            "decision_notes",
            "decided_at",
        ]
    )

    # Create a separate refund transaction.
    # The original charge in OrderLedger remains unchanged.
    RefundLedgerEntry.objects.create(
        original_charge=ledger_entry,
        refund_request=refund_request,
        amount=approved_amount,
        operator=operator,
    )

    # Determine the order's new status using the cumulative refund amount.
    new_total_refunded = money(
        total_refunded + approved_amount
    )

    order = refund_request.order

    if new_total_refunded >= ledger_entry.total_charge:
        if order.status != Order.Status.REFUNDED:
            previous_status = order.status

            order.transition(Order.Status.REFUNDED)
            order.save(update_fields=["status"])

            record_order_status_event(
                order=order,
                from_status=previous_status,
                to_status=order.status,
                actor=operator,
            )

    elif order.status != Order.Status.PARTIALLY_REFUNDED:
        previous_status = order.status

        order.transition(Order.Status.PARTIALLY_REFUNDED)
        order.save(update_fields=["status"])

        record_order_status_event(
            order=order,
            from_status=previous_status,
            to_status=order.status,
            actor=operator,
        )

    return refund_request


REFUND_REQUEST_WINDOW_HOURS = 48


def evaluate_refund_eligibility(refund_request):
    """
    Evaluate whether a refund request meets the refund policy.

    This function does not approve or reject the refund.
    It returns eligibility information for the operator.
    """

    order = refund_request.order

    result = {
        "eligibility_status": "eligible",
        "eligibility_reasons": [],
        "suggested_refund_type": "operator_review",
        "maximum_refundable_amount": "0.00",
    }

    # Rule 1: The order must have reached a final state.
    allowed_statuses = [
        Order.Status.DELIVERED,
        Order.Status.REJECTED,
        Order.Status.CANCELLED,
        Order.Status.PARTIALLY_REFUNDED,
    ]

    if order.status not in allowed_statuses:
        result["eligibility_status"] = "ineligible"
        result["eligibility_reasons"].append(
            "The order has not reached an eligible final state."
        )
        return result

    # Rule 2: An original ledger charge must exist.
    try:
        ledger_entry = OrderLedger.objects.get(order=order)
    except OrderLedger.DoesNotExist:
        result["eligibility_status"] = "ineligible"
        result["eligibility_reasons"].append(
            "No original ledger entry exists for this order."
        )
        return result

    # Rule 3: Calculate the remaining refundable balance.
    total_refunded = get_total_refunded(ledger_entry)
    remaining_amount = money(
        ledger_entry.total_charge - total_refunded
    )

    result["maximum_refundable_amount"] = str(remaining_amount)

    if remaining_amount <= Decimal("0.00"):
        result["eligibility_status"] = "ineligible"
        result["eligibility_reasons"].append(
            "The order has already been fully refunded."
        )
        return result

    # Rule 4: The customer must be the owner of the order.
    if refund_request.customer_id != order.customer_id:
        result["eligibility_status"] = "ineligible"
        result["eligibility_reasons"].append(
            "The refund requester is not the customer who placed the order."
        )
        return result

    # Rule 5: The request must be within the 48-hour request window.
    deadline = ledger_entry.finalized_at + timedelta(
        hours=REFUND_REQUEST_WINDOW_HOURS
    )

    if refund_request.created_at > deadline:
        result["eligibility_status"] = "manual_review"
        result["eligibility_reasons"].append(
            "The request was submitted more than 48 hours after "
            "the order was finalized. An operator exception is required."
        )

    # Rule 6: The requested amount must be valid.
    if refund_request.requested_amount is not None:
        requested_amount = money(
            refund_request.requested_amount
        )

        if requested_amount <= Decimal("0.00"):
            result["eligibility_status"] = "ineligible"
            result["eligibility_reasons"].append(
                "The requested amount must be greater than zero."
            )
            return result

        if requested_amount > remaining_amount:
            result["eligibility_status"] = "ineligible"
            result["eligibility_reasons"].append(
                "The requested amount exceeds the remaining refundable balance."
            )
            return result

    # Rule 7: Determine the type of refund that should be reviewed.
    full_refund_reasons = [
        RefundRequest.Reason.NOT_RECEIVED,
        RefundRequest.Reason.RESTAURANT_CANCELLED,
        RefundRequest.Reason.REJECTED_ORDER,
    ]

    partial_refund_reasons = [
        RefundRequest.Reason.MISSING_ITEMS,
        RefundRequest.Reason.INCORRECT_ITEMS,
        RefundRequest.Reason.DAMAGED_ITEMS,
    ]

    if refund_request.reason in full_refund_reasons:
        result["suggested_refund_type"] = "full_refund_review"
        result["eligibility_reasons"].append(
            "This reason may qualify for a full refund, subject to "
            "operator verification."
        )

    elif refund_request.reason in partial_refund_reasons:
        result["suggested_refund_type"] = "partial_refund_review"
        result["eligibility_reasons"].append(
            "This reason may qualify for a partial refund based on "
            "the value of the affected items and supporting evidence."
        )

    elif refund_request.reason == RefundRequest.Reason.DUPLICATE_PAYMENT:
        result["eligibility_status"] = "manual_review"
        result["suggested_refund_type"] = "duplicate_payment_review"
        result["eligibility_reasons"].append(
            "The operator must verify that a duplicate payment occurred."
        )

    else:
        result["eligibility_status"] = "manual_review"
        result["suggested_refund_type"] = "operator_review"
        result["eligibility_reasons"].append(
            "This reason requires individual operator investigation."
        )

    # Rule 8: Cancelled and rejected orders require payment verification.
    # The existing ledger records calculated charges, which do not
    # necessarily prove that money was actually captured.
    if order.status in [
        Order.Status.REJECTED,
        Order.Status.CANCELLED,
    ]:
        result["eligibility_status"] = "manual_review"
        result["eligibility_reasons"].append(
            "Verify that the customer was actually charged before "
            "approving a refund."
        )

    return result