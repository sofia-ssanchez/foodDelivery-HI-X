from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from guards.permissions import RequireCourier
from dispatch.events import courier_available_publisher

from .commands import (
    AcceptOfferCommand,
    ChangeDutyCommand,
    ConfirmDeliveryCommand,
    ConfirmPickupCommand,
    DeclineOfferCommand,
)
from .models import Courier, DeliveryAssignment
from .serializers import CourierSerializer, DeliveryAssignmentSerializer, DutySerializer


class CourierActivityView(APIView):
    permission_classes = [RequireCourier]

    def get(self, request):
        courier = get_object_or_404(Courier, user=request.user)
        assignments = DeliveryAssignment.objects.filter(courier=courier).select_related(
            "order", "order__restaurant", "order__customer"
        ).prefetch_related("order__lines__menu_item")
        offers = assignments.filter(
            courier=courier,
            status=DeliveryAssignment.Status.OFFERED,
        ).select_related("order", "order__restaurant")
        active = assignments.filter(
            courier=courier,
            status=DeliveryAssignment.Status.ACCEPTED,
        ).select_related("order", "order__restaurant").first()
        return Response({
            "courier": CourierSerializer(courier).data,
            "history": DeliveryAssignmentSerializer(assignments.exclude(
                status__in=[DeliveryAssignment.Status.OFFERED, DeliveryAssignment.Status.ACCEPTED]
            ), many=True).data,
            "offers": DeliveryAssignmentSerializer(offers, many=True).data,
            "active_assignment": (
                DeliveryAssignmentSerializer(active).data if active else None
            ),
        })


class CourierDutyView(APIView):
    permission_classes = [RequireCourier]

    def patch(self, request):
        serializer = DutySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        courier = ChangeDutyCommand(
            actor=request.user,
            on_duty=serializer.validated_data["on_duty"],
        ).execute()
        if courier.status == Courier.Status.IDLE:
            transaction.on_commit(lambda: courier_available_publisher.notify(courier))
        return Response(CourierSerializer(courier).data)


class CourierAssignmentActionView(APIView):
    permission_classes = [RequireCourier]
    command_class = None

    def post(self, request, assignment_id):
        assignment = self.command_class(
            actor=request.user,
            assignment_id=assignment_id,
        ).execute()
        assignment = DeliveryAssignment.objects.select_related(
            "order", "order__restaurant"
        ).get(pk=assignment.pk)
        return Response(DeliveryAssignmentSerializer(assignment).data)


class AcceptOfferView(CourierAssignmentActionView):
    command_class = AcceptOfferCommand


class DeclineOfferView(CourierAssignmentActionView):
    command_class = DeclineOfferCommand


class ConfirmPickupView(CourierAssignmentActionView):
    command_class = ConfirmPickupCommand


class ConfirmDeliveryView(CourierAssignmentActionView):
    command_class = ConfirmDeliveryCommand
