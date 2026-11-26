from django.urls import path

from .views import (
    OrderSummaryView,
    CheckoutQuoteView,
    OperatorLedgerView,
    CustomerRefundRequestView,
    OperatorRefundRequestListView,
    OperatorRefundDecisionView,
)

urlpatterns = [
    path("checkout/quote/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path(
        "orders/<int:order_id>/summary/",
        OrderSummaryView.as_view(),
        name="order-summary",
    ),
    path(
        "ledger/",
        OperatorLedgerView.as_view(),
        name="operator-ledger",
    ),
    path(
        "refunds/",
        CustomerRefundRequestView.as_view(),
        name="customer-refund-request",
    ),
    path(
        "operator/refunds/",
        OperatorRefundRequestListView.as_view(),
        name="operator-refund-requests",
    ),
    path(
        "operator/refunds/<int:refund_id>/decision/",
        OperatorRefundDecisionView.as_view(),
        name="operator-refund-decision",
    ),
]