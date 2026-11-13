"""Connect the order-ready publisher to its dispatcher."""

from .dispatcher import Dispatcher
from .publishers import OrderReadyPublisher


dispatcher = Dispatcher()
order_ready_publisher = OrderReadyPublisher()
order_ready_publisher.subscribe(dispatcher)
