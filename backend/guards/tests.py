from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .authentication import CookieJWTAuthentication


class CookieJWTAuthenticationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory(enforce_csrf_checks=True)
        self.authentication = CookieJWTAuthentication()
        self.user = get_user_model().objects.create_user(
            username="courier-test",
            password="test-password-only",
            role="courier",
        )
        self.access_token = AccessToken.for_user(self.user)

    def make_request(self, method="get", token=None, csrf=False, **headers):
        request = getattr(self.factory, method)("/test/", **headers)
        if token is not None:
            request.COOKIES["access_token"] = str(token)
        if csrf:
            # Simulate Django issuing a CSRF cookie and the client returning
            # the corresponding masked token in its request header.
            csrf_request = self.factory.get("/csrf/")
            request.META[settings.CSRF_HEADER_NAME] = get_token(csrf_request)
            request.COOKIES[settings.CSRF_COOKIE_NAME] = csrf_request.META[
                "CSRF_COOKIE"
            ]
        return Request(request)

    def test_valid_access_token_returns_current_database_user(self):
        # Authorization must see current database values, not stale claims.
        self.access_token["role"] = "customer"
        request = self.make_request(token=self.access_token)

        user, validated_token = self.authentication.authenticate(request)

        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(user.role, "courier")
        self.assertEqual(validated_token["jti"], self.access_token["jti"])

    def test_missing_cookie_returns_no_authentication(self):
        self.assertIsNone(
            self.authentication.authenticate(self.make_request())
        )

    def test_malformed_token_is_rejected(self):
        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token="not-a-jwt")
            )

    def test_tampered_signature_is_rejected(self):
        header, payload, signature = str(self.access_token).split(".")
        replacement = "A" if signature[0] != "A" else "B"
        tampered_token = ".".join(
            [header, payload, replacement + signature[1:]]
        )

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token=tampered_token)
            )

    def test_expired_access_token_is_rejected(self):
        self.access_token.set_exp(lifetime=timedelta(seconds=-60))

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token=self.access_token)
            )

    def test_refresh_token_cannot_authenticate(self):
        refresh_token = RefreshToken.for_user(self.user)

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token=refresh_token)
            )

    def test_deleted_user_is_rejected(self):
        self.user.delete()

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token=self.access_token)
            )

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(AuthenticationFailed):
            self.authentication.authenticate(
                self.make_request(token=self.access_token)
            )

    def test_get_does_not_require_csrf_token(self):
        user, _ = self.authentication.authenticate(
            self.make_request(token=self.access_token)
        )
        self.assertEqual(user.pk, self.user.pk)

    def test_unsafe_methods_require_csrf(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                with self.assertRaises(PermissionDenied):
                    self.authentication.authenticate(
                        self.make_request(method, token=self.access_token)
                    )

    def test_mismatched_csrf_token_is_rejected(self):
        request = self.make_request("post", token=self.access_token, csrf=True)
        other_request = self.factory.get("/csrf/")
        request.META[settings.CSRF_HEADER_NAME] = get_token(other_request)

        with self.assertRaises(PermissionDenied):
            self.authentication.authenticate(request)

    def test_matching_csrf_token_allows_post(self):
        request = self.make_request(
            "post",
            token=self.access_token,
            csrf=True,
            HTTP_ORIGIN="http://testserver",
        )

        user, _ = self.authentication.authenticate(request)

        self.assertEqual(user.pk, self.user.pk)

    def test_untrusted_origin_is_rejected_even_with_valid_csrf_token(self):
        request = self.make_request(
            "post",
            token=self.access_token,
            csrf=True,
            HTTP_ORIGIN="https://untrusted.example",
        )

        with self.assertRaises(PermissionDenied):
            self.authentication.authenticate(request)
