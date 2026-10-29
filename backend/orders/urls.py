from django.urls import path
from .dashboard_views import (
    CustomerOrderListView, OperatorOverviewView, RestaurantListView,
    RestaurantMenuView, RestaurantOrderBoardView,
)
from .views import PlaceOrderView, RestaurantOrderStatusView

urlpatterns = [
    path("customer/orders/", CustomerOrderListView.as_view(), name="customer-orders"),
    path("operator/overview/", OperatorOverviewView.as_view(), name="operator-overview"),
    path("restaurant/orders/", RestaurantOrderBoardView.as_view(), name="restaurant-orders"),
    path("restaurant/orders/<int:pk>/status/", RestaurantOrderStatusView.as_view(), name="restaurant-order-status"),
    path(
        "restaurants/",
        RestaurantListView.as_view(),
        name="restaurant-list",
    ),
    path(
        "restaurants/<int:restaurant_id>/menu/",
        RestaurantMenuView.as_view(),
        name="restaurant-menu",
    ),
    path(
        "orders/",
        PlaceOrderView.as_view(),
        name="place-order",
    ),
]
