from django.urls import path
from .views import RestaurantListView, RestaurantMenuView

urlpatterns = [
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
]
