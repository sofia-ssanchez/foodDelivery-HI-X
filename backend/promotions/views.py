from django.shortcuts import get_object_or_404
from rest_framework import generics

from guards.permissions import RequireRestaurantUser
from .models import Promotion
from .serializers import PromotionSerializer


class RestaurantPromotionListCreateView(generics.ListCreateAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = PromotionSerializer

    def get_queryset(self):
        return Promotion.objects.filter(restaurant__owner=self.request.user).select_related("restaurant")


class RestaurantPromotionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [RequireRestaurantUser]
    serializer_class = PromotionSerializer

    def get_queryset(self):
        return Promotion.objects.filter(restaurant__owner=self.request.user).select_related("restaurant")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["promotion_id"])
