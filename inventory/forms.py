from django import forms
from django.core.exceptions import ValidationError
from .models import Asset, Loan, Person, Desk, Office


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["category", "name", "serial_number", "asset_tag", "status", "purchase_date", "notes"]


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ["first_name", "last_name", "department", "email"]


class LoanForm(forms.ModelForm):
    TARGET_CHOICES = [
        ("person", "Person"),
        ("desk", "Desk"),
        ("office", "Office"),
        ("department", "Department"),
    ]
    target_type = forms.ChoiceField(choices=TARGET_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = Loan
        fields = ["asset", "person", "desk", "office", "department", "due_date", "issued_by"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only available assets can be loaned
        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")

        # Optional: order lists
        self.fields["person"].queryset = Person.objects.order_by("last_name", "first_name")
        self.fields["desk"].queryset = Desk.objects.select_related("room__office").order_by("room__office__name", "room__name", "code")
        self.fields["office"].queryset = Office.objects.order_by("name")

        # make these non-required; we validate manually
        self.fields["person"].required = False
        self.fields["desk"].required = False
        self.fields["office"].required = False
        self.fields["department"].required = False

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get("target_type")
        asset = cleaned.get("asset")

        if not asset:
            raise ValidationError("Asset is required.")

        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

        # exactly one target, based on target_type
        person = cleaned.get("person")
        desk = cleaned.get("desk")
        office = cleaned.get("office")
        department = (cleaned.get("department") or "").strip()

        # wipe unused targets
        cleaned["person"] = None
        cleaned["desk"] = None
        cleaned["office"] = None
        cleaned["department"] = None

        if target_type == "person":
            if not person:
                raise ValidationError("Select a person.")
            cleaned["person"] = person

        elif target_type == "desk":
            if not desk:
                raise ValidationError("Select a desk.")
            cleaned["desk"] = desk

        elif target_type == "office":
            if not office:
                raise ValidationError("Select an office.")
            cleaned["office"] = office

        elif target_type == "department":
            if not department:
                raise ValidationError("Enter a department.")
            cleaned["department"] = department

        else:
            raise ValidationError("Choose loan target type.")

        return cleaned
