"""Simple role system based on Django Groups.

We keep roles lightweight because:
- Django admin already understands Groups
- Later (order validation etc.) we can use role checks consistently

Roles in this project:
- admin: full access (admin site + everything)
- employee: authenticated user without admin site
- company: authenticated user without admin site

Note: "admin" is enforced via is_staff/is_superuser, not only by group.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, AbstractUser
from django.contrib.auth.decorators import user_passes_test

ROLE_ADMIN = "admin"
ROLE_EMPLOYEE = "employee"
ROLE_COMPANY = "company"

ROLE_NAMES = (ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_COMPANY)


def get_user_role(user: AbstractUser) -> str:
    """Best-effort role detection.

    - superuser/staff -> admin
    - otherwise first matching group
    - fallback -> employee
    """
    if not user or not getattr(user, "is_authenticated", False):
        return ROLE_EMPLOYEE

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return ROLE_ADMIN

    qs = user.groups.values_list("name", flat=True)
    for name in qs:
        if name in ROLE_NAMES:
            return name
    return ROLE_EMPLOYEE


def ensure_role_groups_exist() -> None:
    """Create required groups if missing."""
    for name in ROLE_NAMES:
        Group.objects.get_or_create(name=name)


def role_required(*allowed_roles: str):
    """Decorator for views.

    - If user is not authenticated -> redirect to login (handled by @login_required)
    - If authenticated but role not allowed -> 403
    """

    allowed = set(allowed_roles)

    def decorator(view_func):
        from functools import wraps
        from django.core.exceptions import PermissionDenied

        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if get_user_role(request.user) not in allowed:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
