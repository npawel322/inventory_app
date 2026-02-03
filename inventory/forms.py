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


def _bootstrapify(form: forms.Form) -> None:
    """Add basic Bootstrap classes without fighting Django widgets."""
    for name, field in form.fields.items():
        w = field.widget
        css = w.attrs.get("class", "")
        if isinstance(w, (forms.Select, forms.SelectMultiple)):
            base = "form-select"
        elif isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
            base = css  # don't force
        else:
            base = "form-control"
        if base and base not in css:
            w.attrs["class"] = (css + " " + base).strip()


class AdminLoanForm(forms.ModelForm):
    """Admin can create loans to any target type (person/desk/office/department)."""

    TARGET_CHOICES = [
        ("person", "Person"),
        ("desk", "Desk"),
        ("office", "Office"),
        ("department", "Department"),
    ]
    target_type = forms.ChoiceField(choices=TARGET_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = Loan
        fields = ["asset", "target_type", "person", "desk", "office", "department", "loan_date", "due_date"]

        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["person"].queryset = Person.objects.order_by("last_name", "first_name")
        self.fields["desk"].queryset = Desk.objects.select_related("room__office").order_by(
            "room__office__name", "room__name", "code"
        )
        self.fields["office"].queryset = Office.objects.order_by("name")

        self.fields["person"].required = False
        self.fields["desk"].required = False
        self.fields["office"].required = False
        self.fields["department"].required = False

        _bootstrapify(self)

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get("target_type")
        asset = cleaned.get("asset")

        if not asset:
            raise ValidationError("Asset is required.")
        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

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


class CompanyLoanForm(forms.ModelForm):
    """Company can loan to a department within an office."""

    class Meta:
        model = Loan
        fields = ["asset", "office", "department", "loan_date", "due_date"]

        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["office"].queryset = Office.objects.order_by("name")

        self.fields["office"].required = True
        self.fields["department"].required = True

        _bootstrapify(self)

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        if not asset:
            raise ValidationError("Asset is required.")
        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

        if not cleaned.get("office"):
            raise ValidationError("Office is required.")
        department = (cleaned.get("department") or "").strip()
        if not department:
            raise ValidationError("Department is required.")
        cleaned["department"] = department
        return cleaned


class EmployeeLoanForm(forms.ModelForm):
    """Employee loans for themselves: person auto, desk selectable."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["office"].queryset = Office.objects.order_by("name")
        self.fields["desk"].queryset = Desk.objects.select_related("room__office").order_by(
            "room__office__name", "room__name", "code"
        )

        self.fields["office"].required = True
        self.fields["department"].required = True
        self.fields["desk"].required = True

        _bootstrapify(self)

    class Meta:
        model = Loan
        fields = ["asset", "office", "department", "desk", "loan_date", "due_date"]

        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def _resolve_person(self) -> Person | None:
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return None

        # 1) explicit link
        if hasattr(self.user, "person_profile"):
            try:
                return self.user.person_profile
            except Person.DoesNotExist:
                pass

        # 2) match by email (nice fallback)
        email = getattr(self.user, "email", "") or ""
        if email:
            return Person.objects.filter(email__iexact=email).first()

        return None

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        if not asset:
            raise ValidationError("Asset is required.")
        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

        if not cleaned.get("office"):
            raise ValidationError("Office is required.")
        department = (cleaned.get("department") or "").strip()
        if not department:
            raise ValidationError("Department is required.")
        cleaned["department"] = department

        desk = cleaned.get("desk")
        if not desk:
            raise ValidationError("Desk is required.")

        # sanity: desk must belong to chosen office
        if cleaned.get("office") and desk.room.office_id != cleaned["office"].id:
            raise ValidationError("Selected desk is not in the chosen office.")

        # ensure person exists
        person = self._resolve_person()
        if not person:
            raise ValidationError(
                "Your account is not linked to an employee profile yet. Ask admin to link your user to a Person record (or set matching email)."
            )

        # stash for save()
        self._resolved_person = person
        return cleaned

    def save(self, commit=True):
        loan: Loan = super().save(commit=False)
        loan.person = getattr(self, "_resolved_person", None)
        if commit:
            loan.save()
            self.save_m2m()
        return loan
