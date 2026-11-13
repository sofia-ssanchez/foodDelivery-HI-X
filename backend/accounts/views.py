from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from guards.permissions import RequireAuth
from guards.authentication import enforce_csrf
from guards.cookies import auth_cookie_name
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView as BaseTokenRefreshView

from .serializers import (
    SignupSerializer,
    CustomTokenObtainPairSerializer,
)


class LogoutView(APIView):
    # Allow cookie cleanup even when the access token has expired.
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        enforce_csrf(request)
        response = Response({"message": "Logged out successfully."})
        response["Cache-Control"] = "no-store"
        # CSRF is host-wide and carries no login identity. Keep it so logging
        # out on one frontend does not disrupt requests from another port.
        for cookie in (auth_cookie_name(request, "access"), auth_cookie_name(request, "refresh")):
            response.delete_cookie(cookie, path="/", samesite="Lax")
        return response


class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]


class TokenRefreshView(BaseTokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get(auth_cookie_name(request, "refresh"))
        if not refresh:
            raise InvalidToken("Please log in again.")

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, AuthenticationFailed, get_user_model().DoesNotExist) as exc:
            raise InvalidToken("Your session has expired. Please log in again.") from exc

        response = Response({"message": "Access token refreshed."})
        response["Cache-Control"] = "no-store"
        for token_type in ("access", "refresh"):
            if token_type in serializer.validated_data:
                response.set_cookie(
                    key=auth_cookie_name(request, token_type),
                    value=str(serializer.validated_data[token_type]),
                    httponly=True,
                    secure=not settings.DEBUG,
                    samesite="Lax",
                    path="/",
                )
        return response


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user
        tokens = serializer.validated_data
        # Ask CsrfViewMiddleware to issue the cookie used by frontend POSTs.
        get_token(request)

        response = Response(
            {
                "message": "Login successful.",
                "username": user.username,
                "role": user.role,
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key=auth_cookie_name(request, "access"),
            value=str(tokens["access"]),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
        )

        response.set_cookie(
            key=auth_cookie_name(request, "refresh"),
            value=str(tokens["refresh"]),
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            path="/",
        )

        return response


class CurrentAccountView(APIView):
    permission_classes = [RequireAuth]

    def get(self, request):
        response = Response({"username": request.user.username, "role": request.user.role})
        response["Cache-Control"] = "no-store"
        return response
