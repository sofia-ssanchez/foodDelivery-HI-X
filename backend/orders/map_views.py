"""Role-scoped map data; private locations are filtered before serialization."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.models import Courier, DeliveryAssignment
from guards.permissions import RequireAuth
from .models import Order, Restaurant

ACTIVE_STATUSES = ("placed", "accepted", "preparing", "ready", "picked_up")


class DashboardMapView(APIView):
    permission_classes = [RequireAuth]

    def get(self, request):
        user = request.user
        points, notices = [], []
        restaurants = Restaurant.objects.none()
        couriers = Courier.objects.none()
        highlighted = set()
        active_assignments = DeliveryAssignment.objects.filter(status="accepted")

        if user.role == "customer":
            orders = Order.objects.filter(customer=user, status__in=ACTIVE_STATUSES)
            highlighted = set(orders.values_list("restaurant_id", flat=True))
            restaurants = Restaurant.objects.filter(Q(status="open") | Q(id__in=highlighted))
            couriers = Courier.objects.filter(
                status="carrying", assignments__in=active_assignments.filter(
                    order__customer=user, order__status="picked_up"
                ),
            ).distinct()
            for order in orders.exclude(delivery_latitude=None).exclude(delivery_longitude=None):
                points.append(self.point(f"destination-{order.id}", f"Order #{order.id} · Delivery destination", "customer", order.delivery_latitude, order.delivery_longitude, order.delivery_address or "Saved delivery destination"))
        elif user.role == "restaurant":
            restaurants = Restaurant.objects.filter(owner=user)
            couriers = Courier.objects.filter(
                status="carrying", assignments__in=active_assignments.filter(
                    order__restaurant__owner=user, order__status="picked_up"
                ),
            ).distinct()
        elif user.role == "operator":
            restaurants = Restaurant.objects.all()
            couriers = Courier.objects.select_related("user").all()
        elif user.role == "courier":
            profile = get_object_or_404(Courier, user=user)
            couriers = Courier.objects.filter(pk=profile.pk)
            assignment = active_assignments.filter(courier=profile, order__status__in=ACTIVE_STATUSES).select_related("order").first()
            if assignment:
                order = assignment.order
                restaurants = Restaurant.objects.filter(pk=order.restaurant_id)
                if order.delivery_latitude is not None and order.delivery_longitude is not None:
                    points.append(self.point(f"destination-{order.id}", f"Order #{order.id} · Customer destination", "customer", order.delivery_latitude, order.delivery_longitude, order.delivery_address or "Delivery destination"))
                else:
                    notices.append(f"The customer has not set a delivery location for order #{order.id} yet.")
            else:
                notices.append("Accept a delivery offer to see its restaurant and customer destination.")
        else:
            raise PermissionDenied("This account does not have a dashboard map.")

        for restaurant in restaurants:
            kind = "ordered_restaurant" if restaurant.pk in highlighted else "restaurant"
            detail = f"Status: {restaurant.status}"
            if kind == "ordered_restaurant":
                detail += " · You have an active order here"
            points.append(self.point(f"restaurant-{restaurant.id}", restaurant.name, kind, restaurant.latitude, restaurant.longitude, detail))
        for courier in couriers.select_related("user"):
            points.append(self.point(f"courier-{courier.id}", f"Courier · {courier.user.username}", "courier", courier.latitude, courier.longitude, f"Status: {courier.status}"))
        response = Response({"role": user.role, "points": points, "notices": notices})
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def point(identifier, label, kind, latitude, longitude, detail):
        return {"id": identifier, "label": label, "kind": kind, "latitude": str(latitude), "longitude": str(longitude), "detail": detail}
