import calendar
from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Asset, Department, DepartmentPosition, Desk, Loan, Office, Person


DEFAULT_DEPARTMENTS = [
    "Admin",
    "HR",
    "Finance",
    "IT",
]


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["category", "name", "serial_number", "asset_tag", "status", "purchase_date", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _bootstrapify(self)

        # date picker
        if "purchase_date" in self.fields:
            self.fields["purchase_date"].widget = forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            )



class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ["first_name", "last_name", "department", "email"]


def _bootstrapify(form: forms.Form) -> None:
    """Add basic Bootstrap classes without fighting Django widgets."""
    for _, field in form.fields.items():
        widget = field.widget
        css = widget.attrs.get("class", "")
        if isinstance(widget, (forms.Select, forms.SelectMultiple)):
            base = "form-select"
        elif isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
            base = css  # do not force
        else:
            base = "form-control"
        if base and base not in css:
            widget.attrs["class"] = (css + " " + base).strip()


class DeskByOfficeSelect(forms.Select):
    """Adds office metadata to desk <option> tags for client-side filtering."""

    def __init__(self, *args, desk_office_map=None, **kwargs):
        self.desk_office_map = desk_office_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value is None:
            return option
        raw_value = getattr(value, "value", value)
        office_id = self.desk_office_map.get(str(raw_value))
        if office_id is not None:
            option["attrs"]["data-office-id"] = str(office_id)
        return option


class PersonDepartmentSelect(forms.Select):
    """Adds department metadata to person <option> tags for client-side fill."""

    def __init__(self, *args, person_department_map=None, **kwargs):
        self.person_department_map = person_department_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value is None:
            return option
        raw_value = getattr(value, "value", value)
        department = self.person_department_map.get(str(raw_value))
        if department:
            option["attrs"]["data-department"] = department
        return option


class DepartmentPositionByOfficeSelect(forms.Select):
    """Adds office metadata to department position options."""

    def __init__(self, *args, position_meta_map=None, **kwargs):
        self.position_meta_map = position_meta_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value is None:
            return option
        raw_value = getattr(value, "value", value)
        office_id = self.position_meta_map.get(str(raw_value))
        if office_id is not None:
            option["attrs"]["data-office-id"] = str(office_id)
        return option


def _add_one_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _ensure_default_departments() -> None:
    """Global departments, each with 10 positions."""
    for name in DEFAULT_DEPARTMENTS:
        department, _ = Department.objects.get_or_create(name=name)

        existing = set(department.positions.values_list("number", flat=True))
        missing = [
            DepartmentPosition(department=department, number=idx)
            for idx in range(1, 11)
            if idx not in existing
        ]
        if missing:
            DepartmentPosition.objects.bulk_create(missing)


def _configure_department_field(form: forms.Form) -> None:
    _ensure_default_departments()
    field = form.fields.get("department")
    if not field:
        return
    field.widget = forms.Select()
    field.choices = [("", "---------")] + [
        (d.name, d.name) for d in Department.objects.order_by("name")
    ]
    _bootstrapify(form)


def _configure_asset_field(form: forms.Form) -> None:
    field = form.fields.get("asset")
    if not field:
        return

    # Replace ModelChoice with plain Choice of unique names
    names = list(
        Asset.objects.filter(status="available")
        .values_list("name", flat=True)
        .distinct()
        .order_by("name")
    )
    form.fields["asset"] = forms.ChoiceField(
        choices=[("", "---------")] + [(n, n) for n in names],
        required=True,
    )
    _bootstrapify(form)


def _resolve_asset_by_name(name: str) -> Asset | None:
    if not name:
        return None
    return Asset.objects.filter(status="available", name=name).order_by("id").first()


def _configure_loan_date_fields(form: forms.Form, *, company_due_default: bool = False) -> None:
    today = timezone.localdate()

    for field_name in ("loan_date", "due_date"):
        field = form.fields.get(field_name)
        if field:
            field.widget.attrs["min"] = today.isoformat()

    if form.is_bound or getattr(form.instance, "pk", None):
        return

    if "loan_date" in form.fields:
        form.fields["loan_date"].initial = today
    if "due_date" in form.fields:
        form.fields["due_date"].initial = _add_one_month(today) if company_due_default else today


def _validate_loan_dates(cleaned: dict) -> None:
    today = timezone.localdate()
    loan_date = cleaned.get("loan_date")
    due_date = cleaned.get("due_date")

    if loan_date and loan_date < today:
        raise ValidationError({"loan_date": "Loan date cannot be earlier than today."})

    if due_date and due_date < today:
        raise ValidationError({"due_date": "Due date cannot be earlier than today."})

    if loan_date and due_date and due_date < loan_date:
        raise ValidationError({"due_date": "Due date cannot be earlier than loan date."})


def _assign_legacy_department_label(loan: Loan) -> None:
    # 1) jeśli wypożyczenie jest na osobę i osoba ma department -> to wygrywa
    if loan.person and loan.person.department:
        loan.department = loan.person.department
        return

    # 2) w pozostałych przypadkach bierz bezpośrednio z pola department
    if not loan.department:
        loan.department = None





class AdminLoanForm(forms.ModelForm):
    """Admin can create loans to a person or an office."""

    TARGET_CHOICES = [
        ("person", "Person"),
        ("office", "Office"),
    ]
    target_type = forms.ChoiceField(choices=TARGET_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = Loan
        fields = [
            "asset",
            "target_type",
            "person",
            "office",
            "department",
            "loan_date",
            "due_date",
        ]
        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _configure_asset_field(self)
        persons_qs = Person.objects.order_by("last_name", "first_name")
        self.fields["person"].queryset = persons_qs
        self.fields["person"].widget = PersonDepartmentSelect(
            person_department_map={
                str(person.pk): (person.department or "").strip()
                for person in persons_qs
            }
        )
        self.fields["person"].widget.choices = self.fields["person"].choices
        self.fields["office"].queryset = Office.objects.order_by("name")
        self.fields["department"] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
        )

        self.fields["person"].required = False
        self.fields["office"].required = False
        self.fields["department"].required = False

        _bootstrapify(self)
        _configure_loan_date_fields(self)

    def clean(self):
        cleaned = super().clean()
        target_type = cleaned.get("target_type")
        asset_name = cleaned.get("asset")
        asset = _resolve_asset_by_name(asset_name)
        if not asset:
            raise ValidationError({"asset": "Asset is required."})
        cleaned["asset"] = asset

        person = cleaned.get("person")
        office = cleaned.get("office")
        department = (cleaned.get("department") or "").strip()

        cleaned["person"] = None
        cleaned["office"] = None
        cleaned["department"] = None

        if target_type == "person":
            if not person:
                raise ValidationError("Select a person.")
            cleaned["person"] = person

            
            cleaned["department"] = (person.department or "").strip() or None

        elif target_type == "office":
            if not office:
                raise ValidationError("Select an office.")
            cleaned["office"] = office

        else:
            raise ValidationError("Choose loan target type.")

        _validate_loan_dates(cleaned)
        return cleaned

    def save(self, commit=True):
        loan: Loan = super().save(commit=False)
        _assign_legacy_department_label(loan)
        if commit:
            loan.save()
            self.save_m2m()
        return loan


class CompanyLoanForm(forms.ModelForm):
    """Company can loan to a department position within an office."""

    class Meta:
        model = Loan
        fields = ["asset", "office", "department", "loan_date", "due_date"]
        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _configure_asset_field(self)
        self.fields["office"].queryset = Office.objects.order_by("name")

        _configure_department_field(self)

        self.fields["office"].required = True
        self.fields["department"].required = True

        _bootstrapify(self)
        _configure_loan_date_fields(self, company_due_default=True)

    def clean(self):
        cleaned = super().clean()
        asset_name = cleaned.get("asset")
        asset = _resolve_asset_by_name(asset_name)
        office = cleaned.get("office")
        department = (cleaned.get("department") or "").strip()

        if not asset:
            raise ValidationError({"asset": "Asset is required."})
        cleaned["asset"] = asset

        if not office:
            raise ValidationError("Office is required.")
        if not department:
            raise ValidationError("Department is required.")

        cleaned["department"] = department

        _validate_loan_dates(cleaned)
        return cleaned

    def save(self, commit=True):
        loan: Loan = super().save(commit=False)
        _assign_legacy_department_label(loan)
        if commit:
            loan.save()
            self.save_m2m()
        return loan


class EmployeeLoanForm(forms.ModelForm):
    """Employee loans for themselves: person auto, desk selectable."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        _configure_asset_field(self)
        self.fields["office"].queryset = Office.objects.order_by("name")

        desks_qs = Desk.objects.select_related("room__office").order_by(
            "room__office__name", "room__name", "code"
        )
        self.fields["desk"].queryset = desks_qs
        self.fields["desk"].widget = DeskByOfficeSelect(
            desk_office_map={str(desk.pk): desk.room.office_id for desk in desks_qs}
        )
        self.fields["desk"].widget.choices = self.fields["desk"].choices

        _configure_department_field(self)

        self.fields["office"].required = True
        self.fields["department"].required = True
        self.fields["desk"].required = True

        _bootstrapify(self)
        _configure_loan_date_fields(self)

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

        if hasattr(self.user, "person_profile"):
            try:
                return self.user.person_profile
            except Person.DoesNotExist:
                pass

        email = getattr(self.user, "email", "") or ""
        if email:
            return Person.objects.filter(email__iexact=email).first()

        return None

    def clean(self):
        cleaned = super().clean()
        asset_name = cleaned.get("asset")
        asset = _resolve_asset_by_name(asset_name)
        office = cleaned.get("office")
        desk = cleaned.get("desk")
        department = (cleaned.get("department") or "").strip()

        if not asset:
            raise ValidationError({"asset": "Asset is required."})
        cleaned["asset"] = asset

        if not office:
            raise ValidationError("Office is required.")
        if not department:
            raise ValidationError("Department is required.")

        if not desk:
            raise ValidationError("Desk is required.")
        if desk.room.office_id != office.id:
            raise ValidationError("Selected desk is not in the chosen office.")

        person = self._resolve_person()
        if not person:
            raise ValidationError(
                "Your account is not linked to an employee profile yet. Ask admin to link your user to a Person record (or set matching email)."
            )

        self._resolved_person = person
        cleaned["department"] = department
        _validate_loan_dates(cleaned)
        return cleaned

    def save(self, commit=True):
        loan: Loan = super().save(commit=False)
        loan.person = getattr(self, "_resolved_person", None)
        _assign_legacy_department_label(loan)
        if commit:
            loan.save()
            self.save_m2m()
        return loan
