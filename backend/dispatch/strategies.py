"""Courier selection using geographic distance to the restaurant."""
""" add other dispatch strategies here as needed """

from math import atan2, cos, radians, sin, sqrt

from delivery.models import Courier
from orders.models import Order, Restaurant
from .interfaces import DispatchStrategy


def distance_to_restaurant(courier: Courier, restaurant: Restaurant,) -> float:

    lat1 = radians(float(courier.latitude))
    lon1 = radians(float(courier.longitude))
    lat2 = radians(float(restaurant.latitude))
    lon2 = radians(float(restaurant.longitude))

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    a = min(1.0, max(0.0, a))

    return 6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a))


class NearestIdleCourierStrategy(DispatchStrategy):

    def select_courier(self, order: Order, couriers: list[Courier]) -> Courier | None:
        """Select from eligible idle couriers supplied by the caller."""
        closest_courier = None
        closest_distance = float("inf")

        for courier in couriers:
            if courier.latitude is None or courier.longitude is None:
                continue

            distance = distance_to_restaurant(courier, order.restaurant)

            if (
                closest_courier is None
                or distance < closest_distance
                or (
                    distance == closest_distance
                    and courier.user_id < closest_courier.user_id
                )
            ):
                closest_courier = courier
                closest_distance = distance

        return closest_courier
