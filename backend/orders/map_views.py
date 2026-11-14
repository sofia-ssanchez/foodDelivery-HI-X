"""Role-scoped map data; private locations are filtered before serialization."""
from django.db.models import Count
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
            restaurants = Restaurant.objects.all()
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
            couriers = Courier.objects.select_related("user").exclude(
                status=Courier.Status.OFFLINE
            )
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

        restaurants = list(restaurants.prefetch_related("menu_items"))
        restaurant_ids = [restaurant.pk for restaurant in restaurants]
        counts = {}
        for row in Order.objects.filter(restaurant_id__in=restaurant_ids).values("restaurant_id", "status").annotate(total=Count("id")):
            counts.setdefault(row["restaurant_id"], {})[row["status"]] = row["total"]
        visible_orders = Order.objects.filter(restaurant_id__in=restaurant_ids, status__in=ACTIVE_STATUSES)
        if user.role == "customer":
            visible_orders = visible_orders.filter(customer=user)
        elif user.role == "courier":
            visible_orders = visible_orders.filter(delivery_assignments__courier__user=user, delivery_assignments__status="accepted")
        orders_by_restaurant = {}
        for order in visible_orders.order_by("created_at", "id"):
            orders_by_restaurant.setdefault(order.restaurant_id, []).append(order)

        for restaurant in restaurants:
            kind = "ordered_restaurant" if restaurant.pk in highlighted else "restaurant"
            detail = f"Status: {restaurant.status}"
            if kind == "ordered_restaurant":
                detail += " · You have an active order here"
            stats = counts.get(restaurant.pk, {})
            queued = stats.get("placed", 0) + stats.get("accepted", 0)
            color = "red" if restaurant.status == "paused" or queued >= 6 else "amber" if queued >= 3 else "green"
            visible = orders_by_restaurant.get(restaurant.pk, [])
            heads = {state: next((order.pk for order in visible if order.status == state), None) for state in ("placed", "accepted")}
            rows = []
            for order in visible:
                actions = []
                if user.role == "restaurant":
                    targets = []
                    if order.status == "placed" and order.pk == heads["placed"]:
                        targets = [("Accept", "accepted"), ("Reject", "rejected")]
                    elif order.status == "accepted" and order.pk == heads["accepted"]:
                        targets = [("Start preparing", "preparing")]
                    elif order.status == "preparing":
                        targets = [("Mark ready", "ready")]
                    actions = [{"label": label, "url": f"/api/restaurant/orders/{order.pk}/status/", "method": "PATCH",
                                "body": {"status": target, "expected_status": order.status}} for label, target in targets]
                elif user.role == "courier" and profile.status in ("assigned", "carrying"):
                    action = "pickup" if order.status == "ready" else "deliver" if order.status == "picked_up" else None
                    if action:
                        actions = [{"label": "Confirm pickup" if action == "pickup" else "Confirm delivered",
                                    "url": f"/api/delivery/assignments/{assignment.pk}/{action}/", "method": "POST", "body": {}}]
                elif user.role == "operator" and order.status == Order.Status.READY:
                    stalled = order.delivery_assignments.filter(
                        status=DeliveryAssignment.Status.ACCEPTED,
                        picked_up_at__isnull=True,
                        courier__status=Courier.Status.OFFLINE,
                    ).first()
                    if stalled:
                        eligible = Courier.objects.select_related("user").filter(
                            status=Courier.Status.IDLE,
                            user__is_active=True,
                            user__role="courier",
                        ).exclude(
                            assignments__status__in=(
                                DeliveryAssignment.Status.OFFERED,
                                DeliveryAssignment.Status.ACCEPTED,
                            )
                        ).order_by("id")
                        actions = [{
                            "label": f"Reassign to {target.user.username}",
                            "url": f"/api/delivery/operator/assignments/{stalled.pk}/reassign/",
                            "method": "POST",
                            "body": {"courier_id": str(target.pk)},
                        } for target in eligible]
                rows.append({"id": order.pk, "status": order.status, "created_at": order.created_at, "actions": actions})
            point = self.point(f"restaurant-{restaurant.id}", restaurant.name, kind, restaurant.latitude, restaurant.longitude, detail)
            point["restaurant"] = {
                "id": restaurant.pk, "status": restaurant.status, "queue_color": color,
                "queued": queued, "preparing": stats.get("preparing", 0), "ready": stats.get("ready", 0),
                "orders": rows,
                "menu": [{"id": item.pk, "name": item.name, "price": str(item.price), "status": item.status} for item in restaurant.menu_items.all()],
                "actions": ([{"label": "Pause restaurant" if restaurant.status == "open" else "Resume restaurant",
                              "url": f"/api/restaurants/{restaurant.pk}/toggle-activity/", "method": "POST", "body": {}}]
                            if user.role == "restaurant" and restaurant.status in ("open", "paused") else []),
            }
            points.append(point)
        for courier in couriers.select_related("user"):
            points.append(self.point(f"courier-{courier.id}", f"Courier · {courier.user.username}", "courier", courier.latitude, courier.longitude, f"Status: {courier.status}"))
        response = Response({"role": user.role, "points": points, "notices": notices})
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def point(identifier, label, kind, latitude, longitude, detail):
        return {"id": identifier, "label": label, "kind": kind, "latitude": str(latitude), "longitude": str(longitude), "detail": detail}
