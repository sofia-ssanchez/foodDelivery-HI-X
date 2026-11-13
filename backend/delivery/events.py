"""Integration events consumed by dispatch and other DLV collaborators."""

from django.dispatch import Signal


# Dispatch should connect receivers for these post-commit events. Receivers get
# these keyword arguments:
#   courier_became_idle: courier_id
#   delivery_offer_declined: assignment_id, order_id, courier_id
#   delivery_assignment_released: assignment_id, order_id, courier_id
#   order_became_ready: order_id
# DLV deliberately does not select couriers, enqueue orders, or retry assignments.
courier_became_idle = Signal()
delivery_offer_declined = Signal()
order_became_ready = Signal()

# An accepted assignment was released before pickup (for example, off duty).
delivery_assignment_released = Signal()
