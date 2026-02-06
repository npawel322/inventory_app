from django.contrib import admin
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Office, Department, DepartmentPosition, Room, Desk, AssetCategory, Asset, Person, Loan
from .roles import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_COMPANY, ROLE_NAMES


ROLE_CHOICES = (
    (ROLE_ADMIN, "Admin"),
    (ROLE_EMPLOYEE, "Employee"),
    (ROLE_COMPANY, "Company"),
)


def _get_role_from_user(user: User) -> str:
    if user.is_superuser or user.is_staff:
        return ROLE_ADMIN

    names = set(user.groups.values_list("name", flat=True))
    for n in ROLE_NAMES:
        if n in names:
            return n

    return ROLE_EMPLOYEE


def _apply_role(user: User, role: str):
    role = role or ROLE_EMPLOYEE

    for n in ROLE_NAMES:
        Group.objects.get_or_create(name=n)

    role_groups = Group.objects.filter(name__in=list(ROLE_NAMES))
    user.groups.remove(*role_groups)

    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)

    if role == ROLE_ADMIN:
        user.is_staff = True
        user.is_superuser = False  # admin is not a superuser
    else:
        user.is_staff = False
        user.is_superuser = False

    user.save(update_fields=["is_staff", "is_superuser"])


def _get_department_choices():
    departments = Department.objects.order_by("name")
    return [("", "---------")] + [(str(dep), str(dep)) for dep in departments]


class UserRoleChangeForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)
    department = forms.ChoiceField(required=False)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["role"].initial = _get_role_from_user(self.instance)
        else:
            self.fields["role"].initial = ROLE_EMPLOYEE

        self.fields["department"].choices = _get_department_choices()
        person = getattr(self.instance, "person_profile", None)
        if person and person.department:
            self.fields["department"].initial = person.department


class UserRoleAddForm(forms.ModelForm):
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)
    department = forms.ChoiceField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "is_active", "role", "department")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].choices = _get_department_choices()

    def save(self, commit=True):
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
    form = UserRoleChangeForm
    add_form = UserRoleAddForm

    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "department")}),
        ("Role", {"fields": ("is_active", "role")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "first_name",
                "last_name",
                "department",
                "is_active",
                "role",
                "password1",
                "password2",
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        role = form.cleaned_data.get("role") or ROLE_EMPLOYEE
        department_label = (form.cleaned_data.get("department") or "").strip() or None
        _apply_role(obj, role)

        if role == ROLE_EMPLOYEE:
            person = None

            if obj.email:
                person = Person.objects.filter(email=obj.email).first()

            if person:
                if person.user_id != obj.id:
                    person.user = obj

                if not person.first_name:
                    person.first_name = obj.first_name or ""
                if not person.last_name:
                    person.last_name = obj.last_name or ""
                if not person.email:
                    person.email = obj.email or ""

                person.department = department_label
                person.save()

            else:
                Person.objects.get_or_create(
                    user=obj,
                    defaults={
                        "first_name": obj.first_name or "",
                        "last_name": obj.last_name or "",
                        "email": obj.email or "",
                        "department": department_label or "",
                    }
                )


admin.site.register(Office)
admin.site.register(Department)
admin.site.register(DepartmentPosition)
admin.site.register(Room)
admin.site.register(Desk)
admin.site.register(AssetCategory)
admin.site.register(Asset)
admin.site.register(Person)
admin.site.register(Loan)
