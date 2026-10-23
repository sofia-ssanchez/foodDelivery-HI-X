"""Order lifecycle rules. States return the destination for an allowed action."""

from django.core.exceptions import ValidationError


class InvalidTransition(ValidationError):
    pass


class OrderState:
    transitions = {}

    def transition(self, action):
        if action not in self.transitions:
            raise InvalidTransition(
                f"Cannot perform '{action}' when the order is '{self.status}'."
            )
        return self.transitions[action]


class PlacedState(OrderState):
    status = "placed"
    transitions = {"accept": "accepted", "reject": "rejected", "cancel": "cancelled"}


class AcceptedState(OrderState):
    status = "accepted"
    transitions = {"start_preparation": "preparing", "cancel": "cancelled"}


class PreparingState(OrderState):
    status = "preparing"
    transitions = {"mark_ready": "ready"}


class ReadyState(OrderState):
    status = "ready"


class RejectedState(OrderState):
    status = "rejected"


class CancelledState(OrderState):
    status = "cancelled"


STATES = {
    state.status: state()
    for state in (
        PlacedState, AcceptedState, PreparingState,
        ReadyState, RejectedState, CancelledState,
    )
}


def get_state(status):
    try:
        return STATES[status]
    except KeyError:
        raise InvalidTransition(f"Unknown order status: '{status}'.") from None
