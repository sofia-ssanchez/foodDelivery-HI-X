from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from accounts.models import User
from orders.models import Order

from .permissions import (
    RequireAuth,
    RequireCourier,
    RequireCustomer,
    RequireOperator,
    RequireOwnOrder,
    RequireRestaurantUser,
    RequireRole,
)


class RoleGuardTests(SimpleTestCase):
    role_guards = (
        (RequireCustomer, User.Role.CUSTOMER),
        (RequireCourier, User.Role.COURIER),
        (RequireRestaurantUser, User.Role.RESTAURANT),
        (RequireOperator, User.Role.OPERATOR),
    )

    def test_require_auth_accepts_active_users_of_every_role(self):
        for role in User.Role.values:
            with self.subTest(role=role):
                request = SimpleNamespace(user=User(id=1, role=role))
                self.assertTrue(RequireAuth().has_permission(request, None))
                print(f"PASS: require auth accepts active users of every role [role={role}]")

    def test_require_auth_rejects_missing_anonymous_and_inactive_users(self):
        for user in (None, AnonymousUser(), User(id=1, is_active=False)):
            with self.subTest(user=type(user).__name__):
                self.assertFalse(
                    RequireAuth().has_permission(SimpleNamespace(user=user), None)
                )
                print(f"PASS: require auth rejects missing anonymous and inactive users [user={type(user).__name__}]")

    def test_each_role_guard_accepts_only_its_role(self):
        for guard, allowed_role in self.role_guards:
            for role in [*User.Role.values, "unknown"]:
                with self.subTest(guard=guard.__name__, role=role):
                    request = SimpleNamespace(user=User(id=1, role=role))
                    self.assertEqual(
                        guard().has_permission(request, None),
                        role == allowed_role,
                    )
                    print(f"PASS: each role guard accepts only its role [guard={guard.__name__}, role={role}]")

    def test_role_guards_reject_missing_anonymous_and_inactive_users(self):
        for guard, role in self.role_guards:
            for user in (None, AnonymousUser(), User(id=1, role=role, is_active=False)):
                with self.subTest(guard=guard.__name__, user=type(user).__name__):
                    self.assertFalse(
                        guard().has_permission(SimpleNamespace(user=user), None)
                    )
                    print(f"PASS: role guards reject missing anonymous and inactive users [guard={guard.__name__}, user={type(user).__name__}]")

    def test_staff_and_superuser_flags_do_not_bypass_role_checks(self):
        for guard, allowed_role in self.role_guards:
            for role in User.Role.values:
                with self.subTest(guard=guard.__name__, role=role):
                    request = SimpleNamespace(
                        user=User(id=1, role=role, is_staff=True, is_superuser=True)
                    )
                    self.assertEqual(
                        guard().has_permission(request, None),
                        role == allowed_role,
                    )
                    print(f"PASS: staff and superuser flags do not bypass role checks [guard={guard.__name__}, role={role}]")

    def test_base_role_guard_denies_access_without_a_configured_role(self):
        request = SimpleNamespace(user=User(id=1, role=User.Role.CUSTOMER))
        self.assertFalse(RequireRole().has_permission(request, None))
        print("PASS: base role guard denies access without a configured role")


class OwnOrderGuardTests(SimpleTestCase):
    def setUp(self):
        self.guard = RequireOwnOrder()
        self.order = Order(id=10, customer_id=1, restaurant_id=20)

    def test_customer_can_access_own_order(self):
        request = SimpleNamespace(user=User(id=1, role=User.Role.CUSTOMER))
        self.assertTrue(self.guard.has_permission(request, None))
        self.assertTrue(self.guard.has_object_permission(request, None, self.order))
        print("PASS: customer can access own order")

    def test_customer_cannot_access_another_customers_order(self):
        request = SimpleNamespace(user=User(id=2, role=User.Role.CUSTOMER))
        self.assertTrue(self.guard.has_permission(request, None))
        self.assertFalse(self.guard.has_object_permission(request, None, self.order))
        print("PASS: customer cannot access another customers order")

    def test_noncustomer_cannot_access_order_even_with_matching_user_id(self):
        for role in (User.Role.RESTAURANT, User.Role.COURIER, User.Role.OPERATOR):
            with self.subTest(role=role):
                request = SimpleNamespace(user=User(id=1, role=role))
                self.assertFalse(self.guard.has_permission(request, None))
                self.assertFalse(
                    self.guard.has_object_permission(request, None, self.order)
                )
                print(f"PASS: noncustomer cannot access order even with matching user id [role={role}]")

    def test_missing_anonymous_and_inactive_users_cannot_access_order(self):
        users = (
            None,
            AnonymousUser(),
            User(id=1, role=User.Role.CUSTOMER, is_active=False),
        )
        for user in users:
            with self.subTest(user=type(user).__name__):
                request = SimpleNamespace(user=user)
                self.assertFalse(self.guard.has_permission(request, None))
                self.assertFalse(
                    self.guard.has_object_permission(request, None, self.order)
                )
                print(f"PASS: missing anonymous and inactive users cannot access order [user={type(user).__name__}]")

    def test_superuser_cannot_access_another_customers_order(self):
        request = SimpleNamespace(
            user=User(id=2, role=User.Role.CUSTOMER, is_staff=True, is_superuser=True)
        )
        self.assertFalse(self.guard.has_object_permission(request, None, self.order))
        print("PASS: superuser cannot access another customers order")
