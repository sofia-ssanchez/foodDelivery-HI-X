from django.urls import path
from .views import (RestaurantListView, RestaurantMenuView, PlaceOrderView,
                    RestaurantOrderBoardView, RestaurantOrderStatusView)

urlpatterns = [
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
