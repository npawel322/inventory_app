from django.contrib import admin
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Office, Room, Desk, AssetCategory, Asset, Person, Loan
from .roles import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_COMPANY, ROLE_NAMES


ROLE_CHOICES = (
    (ROLE_ADMIN, "Admin"),
    (ROLE_EMPLOYEE, "Employee"),
    (ROLE_COMPANY, "Company"),
)


def _get_role_from_user(user: User) -> str:
    # Admin access is defined by staff/superuser
    if user.is_superuser or user.is_staff:
        return ROLE_ADMIN

    names = set(user.groups.values_list("name", flat=True))
    for n in ROLE_NAMES:
        if n in names:
            return n

    return ROLE_EMPLOYEE


def _apply_role(user: User, role: str):
    """
    Apply role safely AFTER user is saved (must have PK).
    Keeps exactly one role group + enforces staff/superuser flags.
    """
    role = role or ROLE_EMPLOYEE

    # Ensure role groups exist
    for n in ROLE_NAMES:
        Group.objects.get_or_create(name=n)

    # Remove only our role groups, keep other groups intact
    role_groups = Group.objects.filter(name__in=list(ROLE_NAMES))
    user.groups.remove(*role_groups)

    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)

    # Enforce admin access strictly via staff/superuser
    if role == ROLE_ADMIN:
        user.is_staff = True
        user.is_superuser = True  # jeśli NIE chcesz rozdawać superuserów, zmień na False
    else:
        user.is_staff = False
        user.is_superuser = False

    user.save(update_fields=["is_staff", "is_superuser"])


class UserRoleChangeForm(forms.ModelForm):
    """Expose a single 'role' field instead of raw groups."""
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["role"].initial = _get_role_from_user(self.instance)
        else:
            self.fields["role"].initial = ROLE_EMPLOYEE


class UserRoleAddForm(forms.ModelForm):
    """User creation form that also sets the role."""
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "is_active", "role")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned

    def save(self, commit=True):
        """
        IMPORTANT: do NOT touch M2M (groups) here.
        Django admin calls save(commit=False) first -> user has no PK yet.
        Role will be applied in UserAdmin.save_model after saving.
        """
        user: User = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """User admin with a single 'role' selector."""
    form = UserRoleChangeForm
    add_form = UserRoleAddForm

    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Role", {"fields": ("is_active", "role")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "is_active", "role", "password1", "password2"),
        }),
    )

    def save_model(self, request, obj, form, change):
        # 1) Save user first (must have PK)
        super().save_model(request, obj, form, change)

        # 2) Now it's safe to apply M2M groups + flags
        role = form.cleaned_data.get("role") or ROLE_EMPLOYEE
        _apply_role(obj, role)


admin.site.register(Office)
admin.site.register(Room)
admin.site.register(Desk)
admin.site.register(AssetCategory)
admin.site.register(Asset)
admin.site.register(Person)
admin.site.register(Loan)
