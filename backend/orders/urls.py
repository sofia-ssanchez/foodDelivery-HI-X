from django.urls import path
from .map_views import DashboardMapView
from .dashboard_views import (
    CustomerOrderListView, OperatorOverviewView, RestaurantListView,
    RestaurantMenuView, RestaurantOrderBoardView, RestaurantPauseActivityView,
)
from .views import (
    AddressLookupView,
    MapLocationView,
    CustomerCancelOrderView,
    OperatorCancelOrderView,
    PlaceOrderView,
    RestaurantOrderStatusView,
)
from .views import PlaceOrderView, RestaurantOrderStatusView, OperatorOrderHistoryView

urlpatterns = [
    path("customer/address-lookup/", AddressLookupView.as_view(), name="checkout-address-lookup"),
    path("map/", DashboardMapView.as_view(), name="dashboard-map"),
    path("map/location/", MapLocationView.as_view(), name="map-location"),
    path(
        "restaurants/<int:pk>/toggle-activity/",
        RestaurantPauseActivityView.as_view(),
        name="restaurant-toggle-activity",
    ),
    path("customer/orders/", CustomerOrderListView.as_view(), name="customer-orders"),
    path("customer/orders/<int:pk>/cancel/", CustomerCancelOrderView.as_view(), name="customer-cancel-order"),
    path("operator/orders/<int:pk>/cancel/", OperatorCancelOrderView.as_view(), name="operator-cancel-order"),
    path("operator/overview/", OperatorOverviewView.as_view(), name="operator-overview"),
    path("operator/orders/", OperatorOrderHistoryView.as_view(), name="operator-order-history"),
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
