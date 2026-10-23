from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    """Apply Django's CSRF checks to a cookie-authenticated request."""
    check = CSRFCheck(lambda request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})

    if reason:
        raise PermissionDenied(f"CSRF failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate an access-token cookie using Simple JWT validation."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)

        enforce_csrf(request)

        return user, validated_token
