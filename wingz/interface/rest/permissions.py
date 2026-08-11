from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allow access only to authenticated users whose role is 'admin'.

    Applied as the project-wide default permission class, so endpoints are admin-only
    unless they deliberately opt out.
    """

    message = "This endpoint is restricted to users with the 'admin' role."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)
