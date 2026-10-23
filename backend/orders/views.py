from rest_framework import generics
from guards.permissions import RequireAuth
from .models import MenuItem, Restaurant
from .commands import PlaceOrderCommand
from .serializers import MenuItemSerializer, PlaceOrderSerializer, RestaurantSerializer

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

class PlaceOrderView(generics.CreateAPIView):
    serializer_class = PlaceOrderSerializer
    permission_classes = [RequireAuth]

    def create(self, request, *args, **kwargs):
        if request.user.role != request.user.Role.CUSTOMER:
            raise PermissionDenied("Only customers can place orders.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        command = PlaceOrderCommand(
            customer=request.user,
            restaurant_id=serializer.validated_data["restaurant_id"],
            items=serializer.validated_data["items"],
        )

        order = command.execute()

        return Response(
            {
                "id": order.id,
                "restaurant_id": order.restaurant_id,
                "status": order.status,
            },
            status=status.HTTP_201_CREATED,
        )
