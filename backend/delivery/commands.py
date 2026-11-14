from abc import ABC, abstractmethod
from functools import wraps
import random
from types import SimpleNamespace
import time

from django.db import IntegrityError, OperationalError, transaction
from orders.event_services import record_order_status_event
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from guards.permissions import RequireCourier, RequireOperator
from orders.models import Order
from pricing.services import record_order_ledger

from . import events
from .models import Courier, DeliveryAssignment


class DeliveryConflict(APIException):
    status_code = 409
    default_detail = "The courier or delivery has changed. Refresh and try again."


def translate_write_races(method):
    """Retry SQLite lock races, then report stale/duplicate writes as a conflict."""
    @wraps(method)
    def wrapped(*args, **kwargs):
        for attempt in range(4):
            try:
                return method(*args, **kwargs)
            except IntegrityError as exc:
                raise DeliveryConflict() from exc
            except OperationalError as exc:
                message = str(exc).lower()
                if "locked" not in message and "busy" not in message:
                    raise
                if attempt == 3:
                    raise DeliveryConflict() from exc
                # SQLite transactions can both read before attempting a write.
                # Let one transaction finish, then retry against the committed state.
                time.sleep((0.015 * (attempt + 1)) + random.uniform(0, 0.02))
    return wrapped


def _transition_courier(courier, target_status):
    previous_status = courier.status
    courier.transition(target_status)
    if not Courier.objects.filter(
        pk=courier.pk, status=previous_status
    ).update(status=target_status):
        raise DeliveryConflict()
    courier.status = target_status


def _transition_order(order, target_status, actor, **timestamps):
    previous_status = order.status
    try:
        order.transition(target_status)
    except ValueError as exc:
        raise DeliveryConflict(str(exc)) from exc
    if not Order.objects.filter(
        pk=order.pk, status=previous_status
    ).update(status=order.status, **timestamps):
        raise DeliveryConflict()
    record_order_status_event(
        order=order,
        from_status=previous_status,
        to_status=order.status,
        actor=actor,
    )


def _active_assignments(courier):
    return DeliveryAssignment.objects.filter(
        courier=courier,
        status__in=(DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED),
    )


def _schedule_event(signal, **kwargs):
    transaction.on_commit(
        lambda: signal.send_robust(sender=DeliveryAssignment, **kwargs)
    )


@translate_write_races
@transaction.atomic
def create_delivery_offer(*, order_id, courier_id):
    """Create one offer after dispatch has selected a courier.

    Dispatch owns selection and queueing. This boundary owns validation and
    persistence, so callers cannot offer an unready order or busy/off-duty courier.
    """
    try:
        courier = Courier.objects.select_for_update().select_related("user").get(
            pk=courier_id
        )
    except Courier.DoesNotExist:
        raise ValidationError("Courier does not exist.") from None

    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist:
        raise ValidationError("Order does not exist.") from None

    if not courier.user.is_active or courier.user.role != courier.user.Role.COURIER:
        raise PermissionDenied("Only active courier accounts can receive offers.")
    if courier.status != Courier.Status.IDLE:
        raise DeliveryConflict("Only an idle, on-duty courier can receive an offer.")
    if order.status != Order.Status.READY:
        raise ValidationError("A delivery offer can only be created for a ready order.")
    if _active_assignments(courier).exists():
        raise DeliveryConflict("This courier already has an active offer or order.")
    if DeliveryAssignment.objects.filter(
        order=order,
        status__in=(DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED),
    ).exists():
        raise DeliveryConflict("This order already has an active courier offer.")

    return DeliveryAssignment.objects.create(order=order, courier=courier)


class CourierCommand(ABC):
    def __init__(self, actor):
        self.actor = actor

    def get_courier(self, *, lock=True):
        if not RequireCourier().has_permission(
            SimpleNamespace(user=self.actor), None
        ):
            raise PermissionDenied("Only active courier accounts can perform this operation.")
        query = Courier.objects.select_related("user")
        if lock:
            query = query.select_for_update()
        try:
            return query.get(user=self.actor)
        except Courier.DoesNotExist:
            raise ValidationError("Courier profile does not exist.") from None

    @abstractmethod
    def execute(self):
        raise NotImplementedError


class ChangeDutyCommand(CourierCommand):
    def __init__(self, actor, on_duty):
        super().__init__(actor)
        self.on_duty = on_duty

    @translate_write_races
    @transaction.atomic
    def execute(self):
        courier = self.get_courier()
        if self.on_duty:
            if courier.status == Courier.Status.OFFLINE:
                accepted = _active_assignments(courier).filter(
                    status=DeliveryAssignment.Status.ACCEPTED
                ).exists()
                target = Courier.Status.ASSIGNED if accepted else Courier.Status.IDLE
                _transition_courier(courier, target)
                if target == Courier.Status.IDLE:
                    _schedule_event(events.courier_became_idle, courier_id=courier.id)
            return courier

        if courier.status == Courier.Status.CARRYING:
            raise ValidationError("A courier cannot go off duty while carrying an order.")

        offer = _active_assignments(courier).filter(
            status=DeliveryAssignment.Status.OFFERED
        ).first()
        if offer:
            declined_at = timezone.now()
            if not DeliveryAssignment.objects.filter(
                pk=offer.pk, status=DeliveryAssignment.Status.OFFERED
            ).update(
                status=DeliveryAssignment.Status.DECLINED,
                declined_at=declined_at,
            ):
                raise DeliveryConflict()
            offer.status = DeliveryAssignment.Status.DECLINED
            offer.declined_at = declined_at
            _schedule_event(
                events.delivery_offer_declined,
                assignment_id=offer.id,
                order_id=offer.order_id,
                courier_id=courier.id,
            )

        accepted = _active_assignments(courier).filter(
            status=DeliveryAssignment.Status.ACCEPTED
        ).first()
        if accepted:
            order = Order.objects.select_for_update().get(pk=accepted.order_id)
            if accepted.picked_up_at or order.status == Order.Status.PICKED_UP:
                raise ValidationError("A courier cannot go off duty while carrying an order.")

        if courier.status != Courier.Status.OFFLINE:
            _transition_courier(courier, Courier.Status.OFFLINE)
        return courier


class AssignmentCommand(CourierCommand):
    def __init__(self, actor, assignment_id):
        super().__init__(actor)
        self.assignment_id = assignment_id

    def get_assignment(self, courier, expected_status):
        try:
            return DeliveryAssignment.objects.select_for_update().get(
                pk=self.assignment_id,
                courier=courier,
                status=expected_status,
            )
        except DeliveryAssignment.DoesNotExist:
            raise DeliveryConflict("This delivery is no longer available for that action.") from None

    @staticmethod
    def get_order(assignment):
        try:
            return Order.objects.select_for_update().get(pk=assignment.order_id)
        except Order.DoesNotExist:
            raise ValidationError("The assigned order no longer exists.") from None


class AcceptOfferCommand(AssignmentCommand):
    @translate_write_races
    @transaction.atomic
    def execute(self):
        courier = self.get_courier()
        assignment = self.get_assignment(courier, DeliveryAssignment.Status.OFFERED)
        order = self.get_order(assignment)
        if courier.status != Courier.Status.IDLE:
            raise DeliveryConflict("Only an idle courier can accept an offer.")
        if order.status != Order.Status.READY:
            raise ValidationError("Only a ready order can be accepted for delivery.")

        accepted_at = timezone.now()
        if not DeliveryAssignment.objects.filter(
            pk=assignment.pk,
            courier=courier,
            status=DeliveryAssignment.Status.OFFERED,
            order__status=Order.Status.READY,
        ).update(
            status=DeliveryAssignment.Status.ACCEPTED,
            accepted_at=accepted_at,
        ):
            raise DeliveryConflict()
        _transition_courier(courier, Courier.Status.ASSIGNED)
        assignment.status = DeliveryAssignment.Status.ACCEPTED
        assignment.accepted_at = accepted_at
        return assignment


class DeclineOfferCommand(AssignmentCommand):
    @translate_write_races
    @transaction.atomic
    def execute(self):
        courier = self.get_courier()
        assignment = self.get_assignment(courier, DeliveryAssignment.Status.OFFERED)
        declined_at = timezone.now()
        if not DeliveryAssignment.objects.filter(
            pk=assignment.pk,
            courier=courier,
            status=DeliveryAssignment.Status.OFFERED,
        ).update(
            status=DeliveryAssignment.Status.DECLINED,
            declined_at=declined_at,
        ):
            raise DeliveryConflict()
        assignment.status = DeliveryAssignment.Status.DECLINED
        assignment.declined_at = declined_at
        _schedule_event(
            events.delivery_offer_declined,
            assignment_id=assignment.id,
            order_id=assignment.order_id,
            courier_id=courier.id,
        )
        return assignment


class ConfirmPickupCommand(AssignmentCommand):
    @translate_write_races
    @transaction.atomic
    def execute(self):
        courier = self.get_courier()
        assignment = self.get_assignment(courier, DeliveryAssignment.Status.ACCEPTED)
        order = self.get_order(assignment)
        if courier.status != Courier.Status.ASSIGNED or assignment.picked_up_at:
            raise DeliveryConflict("This delivery is not awaiting pickup.")
        picked_up_at = timezone.now()
        _transition_order(
            order,
            Order.Status.PICKED_UP,
            courier.user,
            picked_up_at=picked_up_at,
        )
        if not DeliveryAssignment.objects.filter(
            pk=assignment.pk,
            courier=courier,
            status=DeliveryAssignment.Status.ACCEPTED,
            picked_up_at__isnull=True,
        ).update(picked_up_at=picked_up_at):
            raise DeliveryConflict()
        _transition_courier(courier, Courier.Status.CARRYING)
        assignment.picked_up_at = picked_up_at
        return assignment


class ConfirmDeliveryCommand(AssignmentCommand):
    @translate_write_races
    @transaction.atomic
    def execute(self):
        courier = self.get_courier()
        assignment = self.get_assignment(courier, DeliveryAssignment.Status.ACCEPTED)
        order = self.get_order(assignment)
        if courier.status != Courier.Status.CARRYING or order.status != Order.Status.PICKED_UP:
            raise DeliveryConflict("Pickup must be confirmed before delivery.")
        delivered_at = timezone.now()
        _transition_order(
            order,
            Order.Status.DELIVERED,
            courier.user,
            delivered_at=delivered_at,
        )
        if not DeliveryAssignment.objects.filter(
            pk=assignment.pk,
            courier=courier,
            status=DeliveryAssignment.Status.ACCEPTED,
        ).update(
            status=DeliveryAssignment.Status.COMPLETED,
            delivered_at=delivered_at,
        ):
            raise DeliveryConflict()
        _transition_courier(courier, Courier.Status.IDLE)
        assignment.status = DeliveryAssignment.Status.COMPLETED
        assignment.delivered_at = delivered_at
        record_order_ledger(order)
        _schedule_event(events.courier_became_idle, courier_id=courier.id)
        return assignment


class ReassignDeliveryCommand:
    """Let an operator replace an accepted assignment whose courier is offline."""

    def __init__(self, actor, assignment_id, courier_id):
        self.actor = actor
        self.assignment_id = assignment_id
        self.courier_id = courier_id

    @translate_write_races
    @transaction.atomic
    def execute(self):
        if not RequireOperator().has_permission(
            SimpleNamespace(user=self.actor), None
        ):
            raise PermissionDenied("Only active operator accounts can reassign deliveries.")

        try:
            assignment = DeliveryAssignment.objects.select_for_update().get(
                pk=self.assignment_id,
                status=DeliveryAssignment.Status.ACCEPTED,
                picked_up_at__isnull=True,
            )
        except DeliveryAssignment.DoesNotExist:
            raise DeliveryConflict("This assignment is no longer eligible for reassignment.") from None

        order = Order.objects.select_for_update().get(pk=assignment.order_id)
        courier = Courier.objects.select_for_update().get(pk=assignment.courier_id)
        if order.status != Order.Status.READY or courier.status != Courier.Status.OFFLINE:
            raise ValidationError(
                "Only a ready order assigned to an offline courier can be reassigned."
            )

        if not DeliveryAssignment.objects.filter(
            pk=assignment.pk,
            status=DeliveryAssignment.Status.ACCEPTED,
            picked_up_at__isnull=True,
        ).update(status=DeliveryAssignment.Status.REASSIGNED):
            raise DeliveryConflict()

        return create_delivery_offer(
            order_id=order.pk,
            courier_id=self.courier_id,
        )


@translate_write_races
@transaction.atomic
def expire_delivery_offer(*, assignment_id, cutoff):
    """Expire an unanswered offer, preserving accepted assignments."""
    candidate = DeliveryAssignment.objects.filter(pk=assignment_id).values(
        "courier_id"
    ).first()
    if candidate is None:
        return False
    Courier.objects.select_for_update().get(pk=candidate["courier_id"])
    assignment = DeliveryAssignment.objects.select_for_update().filter(
        pk=assignment_id
    ).first()
    if assignment is None:
        return False
    Order.objects.select_for_update().get(pk=assignment.order_id)
    if (assignment.status != DeliveryAssignment.Status.OFFERED
            or assignment.offered_at > cutoff):
        return False
    if not DeliveryAssignment.objects.filter(
        pk=assignment.pk, status=DeliveryAssignment.Status.OFFERED,
        offered_at__lte=cutoff,
    ).update(status=DeliveryAssignment.Status.EXPIRED, expired_at=timezone.now()):
        return False
    _schedule_event(
        events.delivery_offer_expired,
        assignment_id=assignment.pk, order_id=assignment.order_id,
        courier_id=assignment.courier_id,
    )
    return True
