from django.urls import path

from .views import RestaurantPromotionDetailView, RestaurantPromotionListCreateView

urlpatterns = [
    path("", RestaurantPromotionListCreateView.as_view(), name="restaurant-promotions"),
    path("<int:promotion_id>/", RestaurantPromotionDetailView.as_view(), name="restaurant-promotion-detail"),
]
