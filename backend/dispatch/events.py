"""Connect the order-ready publisher to its dispatcher."""

from .dispatcher import Dispatcher
from .publishers import OrderReadyPublisher, CourierAvailabilityPublisher


dispatcher = Dispatcher()
order_ready_publisher = OrderReadyPublisher()
courier_available_publisher = CourierAvailabilityPublisher()
order_ready_publisher.subscribe(dispatcher)
courier_available_publisher.subscribe(dispatcher)

