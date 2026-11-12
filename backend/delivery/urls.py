from django.urls import path

from .views import (
    AcceptOfferView,
    ConfirmDeliveryView,
    ConfirmPickupView,
    CourierActivityView,
    CourierDutyView,
    DeclineOfferView,
)

urlpatterns = [
    path("me/", CourierActivityView.as_view(), name="courier-activity"),
    path("duty/", CourierDutyView.as_view(), name="courier-duty"),
    path("offers/<int:assignment_id>/accept/", AcceptOfferView.as_view(), name="accept-delivery-offer"),
    path("offers/<int:assignment_id>/decline/", DeclineOfferView.as_view(), name="decline-delivery-offer"),
    path("assignments/<int:assignment_id>/pickup/", ConfirmPickupView.as_view(), name="confirm-delivery-pickup"),
    path("assignments/<int:assignment_id>/deliver/", ConfirmDeliveryView.as_view(), name="confirm-delivery-delivery"),
]
