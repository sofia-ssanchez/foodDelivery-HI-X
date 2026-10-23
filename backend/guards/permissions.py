from rest_framework.permissions import BasePermission

from accounts.models import User


class RequireAuth(BasePermission):
    """Require an authenticated, active user."""

    message = "Authentication is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class RequireRole(RequireAuth):
    """Base guard for a specific role on the authenticated database user."""

    role = None
    message = "Your account does not have permission."

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and self.role is not None
            and request.user.role == self.role
        )


class RequireCustomer(RequireRole):
    role = User.Role.CUSTOMER


class RequireCourier(RequireRole):
    role = User.Role.COURIER


class RequireRestaurantUser(RequireRole):
    role = User.Role.RESTAURANT


class RequireOperator(RequireRole):
    role = User.Role.OPERATOR


class RequireOwnOrder(RequireCustomer):
    """Require a customer accessing their own order.

    Views must invoke object permissions when retrieving an order and filter
    list querysets separately to restrict them to the current customer.
    """

    message = "You can only access your own orders."

    def has_object_permission(self, request, view, order):
        return (
            self.has_permission(request, view)
            and order.customer_id == request.user.id
        )



# Restaurant proposal:
# employees and mangers should have different abilities 
#
# from orders.models import RestaurantMembership
#
#
# class RequireRestaurantMembership(RequireRestaurantUser):
#     message = "Membership in this restaurant is required."
#
#     def get_memberships(self, request, view, obj):
#         restaurant_id = view.get_permission_restaurant_id(obj)
#         return RestaurantMembership.objects.filter(
#             user_id=request.user.id,
#             restaurant_id=restaurant_id,
#         )
#
#     def has_object_permission(self, request, view, obj):
#         return (
#             self.has_permission(request, view)
#             and self.get_memberships(request, view, obj).exists()
#         )
#
#
# class RequireRestaurantManager(RequireRestaurantMembership):
#     message = "Manager membership in this restaurant is required."
#
#     def has_object_permission(self, request, view, obj):
#         return (
#             self.has_permission(request, view)
#             and self.get_memberships(request, view, obj).filter(
#                 role=RestaurantMembership.Role.MANAGER,
#             ).exists()
#         )
#
#
# class RequireAssignedCourier(RequireCourier):
#     message = "An active assignment to this delivery is required."
#
#     def has_object_permission(self, request, view, assignment):
#         return (
#             self.has_permission(request, view)
#             and assignment.courier_id == request.user.id
#             and assignment.is_active
#         )
