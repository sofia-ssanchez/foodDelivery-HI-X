from rest_framework import generics
from guards.permissions import RequireAuth
from .models import MenuItem, Restaurant
from .serializers import MenuItemSerializer, RestaurantSerializer

class RestaurantListView(generics.ListAPIView):
    queryset = Restaurant.objects.all()
    serializer_class = RestaurantSerializer
    permission_classes = [RequireAuth]


class RestaurantMenuView(generics.ListAPIView):
    serializer_class = MenuItemSerializer
    permission_classes = [RequireAuth]

    def get_queryset(self):
        return MenuItem.objects.filter(
            restaurant_id=self.kwargs["restaurant_id"]
        )
