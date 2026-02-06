import django_filters
from django import forms

from .models import Asset, Person


class AssetFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        field_name="name",
        lookup_expr="istartswith",
        label="Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Asset name"}),
    )

    serial_number = django_filters.CharFilter(
        field_name="serial_number",
        lookup_expr="istartswith",
        label="Serial",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Serial number"}),
    )

    status = django_filters.MultipleChoiceFilter(
        choices=Asset.STATUS_CHOICES,
        label="Status",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Asset
        fields = ["name", "serial_number", "status"]


class PersonFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        method="filter_name",
        label="Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Name"}),
    )

    email = django_filters.CharFilter(
        field_name="email",
        lookup_expr="istartswith",
        label="Email",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Email"}),
    )

    department = django_filters.MultipleChoiceFilter(
        choices=[],
        label="Department",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Person
        fields = ["name", "email", "department"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        departments = (
            Person.objects.exclude(department__isnull=True)
            .exclude(department__exact="")
            .values_list("department", flat=True)
            .distinct()
            .order_by("department")
        )
        self.filters["department"].extra["choices"] = [(d, d) for d in departments]

    def filter_name(self, queryset, name, value):
        if not value:
            return queryset

        value = value.strip()

        return queryset.filter(
            first_name__istartswith=value
        ) | queryset.filter(
            last_name__istartswith=value
        )
