
from abc import ABC, abstractmethod

class OrderState(ABC):
    @abstractmethod
    def transition(self, targetState):
        pass

class PlacedState(OrderState):
    status = "placed"
    def transition(self, targetState):
        if targetState == "accepted":
            return AcceptedState()
        elif targetState == "rejected":
            return RejectedState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Placed to {targetState}")

class AcceptedState(OrderState):
    status = "accepted"
    def transition(self, targetState):
        if targetState == "preparing":
            return PreparingState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Accepted to {targetState}")

class PreparingState(OrderState):
    status = "preparing"
    def transition(self, targetState):
        if targetState == "ready":
            return ReadyState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Preparing to {targetState}")

class ReadyState(OrderState):
    status = "ready"
    def transition(self, targetState):
        if targetState == "picked_up":
            return PickedUpState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Ready to {targetState}")

class PickedUpState(OrderState):
    status = "picked_up"
    def transition(self, targetState):
        if targetState == "delivered":
            return DeliveredState()
        else:
            raise ValueError(f"Invalid transition from PickedUp to {targetState}")

class DeliveredState(OrderState):
    status = "delivered"
    def transition(self, targetState):
        raise ValueError("Cannot transition from Delivered state")
    
class RejectedState(OrderState):
    status = "rejected"
    def transition(self, targetState):
        raise ValueError("Cannot transition from Rejected state")

class CancelledState(OrderState):
    status = "cancelled"
    def transition(self, targetState):
        raise ValueError("Cannot transition from Cancelled state")


STATE_CLASSES = {
    state.status: state
    for state in (
        PlacedState, AcceptedState, RejectedState, PreparingState,
        ReadyState, PickedUpState, DeliveredState, CancelledState,
    )
}


def get_order_state(status):
    try:
        return STATE_CLASSES[status]()
    except KeyError:
        raise ValueError(f"Unknown order status: {status}") from None
