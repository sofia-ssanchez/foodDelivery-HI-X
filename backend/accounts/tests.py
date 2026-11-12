from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase, APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from guards.cookies import auth_cookie_name


@override_settings(DEBUG=True)
class LocalPortSessionTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        users = get_user_model().objects
        self.restaurant = users.create_user(username="restaurant-port", password="test-password", role="restaurant")
        self.courier = users.create_user(username="courier-port", password="test-password", role="courier")
        self.restaurant_origin = "http://localhost:3000"
        self.courier_origin = "http://localhost:3001"

    def cookie_name(self, origin, token_type):
        request = APIRequestFactory().get("/", HTTP_ORIGIN=origin)
        return auth_cookie_name(request, token_type)

    def login(self, username, origin):
        response = self.client.post("/api/accounts/login/", {
            "username": username, "password": "test-password",
        }, format="json", HTTP_ORIGIN=origin)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.cookies[self.cookie_name(origin, "access")]["httponly"])

    def test_two_ports_keep_their_own_accounts_in_one_cookie_jar(self):
        self.login(self.restaurant.username, self.restaurant_origin)
        self.login(self.courier.username, self.courier_origin)
        for _ in range(2):
            self.assertEqual(self.client.get("/api/restaurant/orders/", HTTP_ORIGIN=self.restaurant_origin).status_code, 200)
            self.assertEqual(self.client.get("/api/delivery/me/", HTTP_ORIGIN=self.courier_origin).status_code, 200)
        self.assertEqual(self.client.get("/api/restaurant/orders/", HTTP_ORIGIN=self.courier_origin).status_code, 403)

    def test_refresh_and_logout_only_affect_the_requesting_port(self):
        self.login(self.restaurant.username, self.restaurant_origin)
        self.login(self.courier.username, self.courier_origin)
        restaurant_cookie = self.cookie_name(self.restaurant_origin, "access")
        original = self.client.cookies[restaurant_cookie].value
        del self.client.cookies[self.cookie_name(self.courier_origin, "access")]
        response = self.client.post("/api/accounts/token/refresh/", HTTP_ORIGIN=self.courier_origin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.cookies[restaurant_cookie].value, original)
        response = self.client.post("/api/accounts/logout/", HTTP_ORIGIN=self.courier_origin,
                                    HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/restaurant/orders/", HTTP_ORIGIN=self.restaurant_origin).status_code, 200)
        self.assertEqual(self.client.post("/api/accounts/token/refresh/", HTTP_ORIGIN=self.courier_origin).status_code, 401)
        # The other port's CSRF-protected requests still work after logout.
        response = self.client.post("/api/accounts/logout/", HTTP_ORIGIN=self.restaurant_origin,
                                    HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)

    def test_new_port_does_not_fall_back_to_a_shared_legacy_login(self):
        self.client.cookies["access_token"] = str(AccessToken.for_user(self.courier))
        self.assertEqual(self.client.get("/api/delivery/me/", HTTP_ORIGIN=self.courier_origin).status_code, 401)

    def test_third_port_is_independent(self):
        self.login(self.courier.username, self.courier_origin)
        self.assertEqual(self.client.get("/api/delivery/me/", HTTP_ORIGIN="http://localhost:3002").status_code, 401)

    @override_settings(DEBUG=False)
    def test_production_keeps_standard_cookie_names(self):
        self.assertEqual(self.cookie_name(self.restaurant_origin, "access"), "access_token")

    def test_logout_still_requires_csrf(self):
        self.login(self.courier.username, self.courier_origin)
        self.assertEqual(self.client.post("/api/accounts/logout/", HTTP_ORIGIN=self.courier_origin).status_code, 403)
