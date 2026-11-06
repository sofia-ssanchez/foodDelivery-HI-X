from django.urls import path
from .views import OrderSummaryView, OperatorLedgerView

urlpatterns = [
    path("orders/<int:order_id>/summary/", OrderSummaryView.as_view(), name="order-summary"),
    path("ledger/", OperatorLedgerView.as_view(), name="operator-ledger"),
]
