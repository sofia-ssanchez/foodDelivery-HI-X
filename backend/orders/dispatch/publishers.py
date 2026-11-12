"""Notify subscribed observers when an order becomes ready."""

from orders.models import Order
from .interfaces import OrderReadyObserver


class OrderReadyPublisher:
    def __init__(self):
        self.observers: list[OrderReadyObserver] = []

    def subscribe(self, observer: OrderReadyObserver) -> None:
        if observer not in self.observers:
            self.observers.append(observer)

    def unsubscribe(self, observer: OrderReadyObserver) -> None:
        if observer in self.observers:
            self.observers.remove(observer)

    def notify(self, order: Order) -> None:
        for observer in list(self.observers):
            observer.on_order_ready(order)
