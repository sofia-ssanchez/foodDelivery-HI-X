from django.urls import path
from .views import OrderSummaryView

urlpatterns = [
    path("orders/<int:order_id>/summary/", OrderSummaryView.as_view(), name="order-summary"),
]
