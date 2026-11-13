from rest_framework.permissions import BasePermission

from .models import User


class IsBroker(BasePermission):
    message = "Only users with the Broker role can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.BROKER)


class IsAnalyst(BasePermission):
    message = "Only users with the Analyst role can perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ANALYST)