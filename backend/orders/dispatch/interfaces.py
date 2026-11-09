"""Contracts for courier selection and dispatch event observers."""

from abc import ABC, abstractmethod

from accounts.models import User
from ..models import Order


class DispatchStrategy(ABC):
    @abstractmethod
    def select_courier(self, order: Order, couriers: list[User]) -> User | None:
        """Choose a courier, or return None if none is eligible."""
        pass


class OrderReadyObserver(ABC):
    @abstractmethod
    def on_order_ready(self, order: Order) -> None:
        """React when an order becomes ready."""
        pass


class CourierAvailabilityObserver(ABC):
    @abstractmethod
    def on_courier_available(self, courier: User) -> None:
        """React when a courier becomes available."""
        pass


class StalledOrderObserver(ABC):
    @abstractmethod
    def on_order_stalled(self, order: Order) -> None:
        """React when an assignment stalls."""
        pass
