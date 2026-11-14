"""Connect the order-ready publisher to its dispatcher."""

from .dispatcher import Dispatcher
from .publishers import OrderReadyPublisher, CourierAvailabilityPublisher


dispatcher = Dispatcher()
order_ready_publisher = OrderReadyPublisher()
courier_available_publisher = CourierAvailabilityPublisher()
order_ready_publisher.subscribe(dispatcher)
courier_available_publisher.subscribe(dispatcher)



from django.dispatch import receiver
from delivery.events import courier_became_idle, delivery_offer_declined, delivery_assignment_released
from delivery.models import Courier


@receiver(delivery_assignment_released, dispatch_uid="dispatch.released_assignment")
@receiver(delivery_offer_declined, dispatch_uid="dispatch.declined_offer")
def reoffer_declined_order(sender, order_id, courier_id, **kwargs):
    dispatcher.on_offer_declined(order_id, courier_id)


@receiver(courier_became_idle, dispatch_uid="dispatch.idle_courier")
def offer_waiting_order(sender, courier_id, **kwargs):
    courier = Courier.objects.filter(pk=courier_id).first()
    if courier is not None:
        dispatcher.on_courier_available(courier)


from delivery.events import delivery_offer_expired
from orders.models import Order
from .publishers import StalledOrderPublisher

stalled_order_publisher = StalledOrderPublisher()
stalled_order_publisher.subscribe(dispatcher)


@receiver(delivery_offer_expired, dispatch_uid="dispatch.expired_offer")
def publish_stalled_order(sender, order_id, **kwargs):
    order = Order.objects.filter(pk=order_id).first()
    if order is not None:
        stalled_order_publisher.notify(order)
