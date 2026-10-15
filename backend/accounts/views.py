from rest_framework import generics
from rest_framework.permissions import AllowAny

from .serializers import SignupSerializer


class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]

