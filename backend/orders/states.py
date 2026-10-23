
from abc import abstractmethod

STATE_CLASSES = {
    "placed": "PlacedState",
    "accepted": "AcceptedState",
    "rejected": "RejectedState",
    "preparing": "PreparingState",
    "ready": "ReadyState",
    "picked_up": "PickedUpState",
    "delivered": "DeliveredState",
    "cancelled": "CancelledState"
}

class OrderState():
    @abstractmethod
    def transition(self, order, targetState):
        pass

class PlacedState(OrderState):
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
    def transition(self, targetState):
        if targetState == "preparing":
            return PreparingState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Accepted to {targetState}")

class PreparingState(OrderState):
    def transition(self, targetState):
        if targetState == "ready":
            return ReadyState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Preparing to {targetState}")

class ReadyState(OrderState):
    def transition(self, targetState):
        if targetState == "picked_up":
            return PickedUpState()
        elif targetState == "cancelled":
            return CancelledState()
        else:
            raise ValueError(f"Invalid transition from Ready to {targetState}")

class PickedUpState(OrderState):
    def transition(self, targetState):
        if targetState == "delivered":
            return DeliveredState()
        else:
            raise ValueError(f"Invalid transition from PickedUp to {targetState}")

class DeliveredState(OrderState):
    def transition(self, targetState):
        raise ValueError("Cannot transition from Delivered state")
    
class RejectedState(OrderState):
    def transition(self, targetState):
        raise ValueError("Cannot transition from Rejected state")

class CancelledState(OrderState):
    def transition(self, targetState):
        raise ValueError("Cannot transition from Cancelled state")
