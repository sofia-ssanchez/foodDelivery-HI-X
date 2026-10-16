from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import MenuItem, Restaurant
from .serializers import MenuItemSerializer, RestaurantSerializer

class RestaurantListView(generics.ListAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [IsAuthenticated]


class RestaurantMenuView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MenuItem.objects.filter(
            restaurant_id=self.kwargs["restaurant_id"]
        )
