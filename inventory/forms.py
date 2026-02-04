import calendar
from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Asset, Department, DepartmentPosition, Desk, Loan, Office, Person


DEFAULT_DEPARTMENTS = [
    ("Yellow", "yellow"),
    ("Blue", "blue"),
    ("Green", "green"),
    ("Purple", "purple"),
    ("Orange", "orange"),
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
    """Each office gets 5 departments and each department 10 positions."""
    for office in Office.objects.all():
        for name, color in DEFAULT_DEPARTMENTS:
            department, _ = Department.objects.get_or_create(
                office=office,
                name=name,
                defaults={"color": color},
            )
            if department.color != color:
                department.color = color
                department.save(update_fields=["color"])

            existing = set(department.positions.values_list("number", flat=True))
            missing = [
                DepartmentPosition(department=department, number=idx)
                for idx in range(1, 11)
                if idx not in existing
            ]
            if missing:
                DepartmentPosition.objects.bulk_create(missing)


def _configure_department_position_field(form: forms.Form) -> None:
    _ensure_default_departments()

    active_position_ids = Loan.objects.filter(
        return_date__isnull=True,
        department_position__isnull=False,
    ).values_list("department_position_id", flat=True)

    positions_qs = DepartmentPosition.objects.select_related("department__office").exclude(
        pk__in=active_position_ids
    ).order_by(
        "department__office__name", "department__name", "number"
    )
    field = form.fields.get("department_position")
    if not field:
        return

    square_by_color = {
        "yellow": "🟨",
        "blue": "🟦",
        "green": "🟩",
        "purple": "🟪",
        "orange": "🟧",
    }

    field.queryset = positions_qs
    field.label_from_instance = (
        lambda pos: f"{square_by_color.get(pos.department.color, '⬜')} #{pos.number}"
    )
    field.widget = DepartmentPositionByOfficeSelect(
        position_meta_map={
            str(pos.pk): pos.department.office_id
            for pos in positions_qs
        }
    )
    field.widget.choices = field.choices


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

    # 2) w pozostałych przypadkach (desk/department) bierz z department_position
    if loan.department_position:
        loan.department = str(loan.department_position)
    elif not loan.department:
        loan.department = None



def _is_department_position_available(position: DepartmentPosition) -> bool:
    return not position.loans.filter(return_date__isnull=True).exists()


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
        fields = [
            "asset",
            "target_type",
            "person",
            "office",
            "desk",
            "department_position",
            "loan_date",
            "due_date",
        ]
        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["person"].queryset = Person.objects.order_by("last_name", "first_name")
        self.fields["office"].queryset = Office.objects.order_by("name")

        desks_qs = Desk.objects.select_related("room__office").order_by(
            "room__office__name", "room__name", "code"
        )
        self.fields["desk"].queryset = desks_qs
        self.fields["desk"].widget = DeskByOfficeSelect(
            desk_office_map={str(desk.pk): desk.room.office_id for desk in desks_qs}
        )
        self.fields["desk"].widget.choices = self.fields["desk"].choices

        _configure_department_position_field(self)

        self.fields["person"].required = False
        self.fields["desk"].required = False
        self.fields["office"].required = False
        self.fields["department_position"].required = False

        _bootstrapify(self)
        _configure_loan_date_fields(self)

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
        department_position = cleaned.get("department_position")

        cleaned["person"] = None
        cleaned["desk"] = None
        cleaned["office"] = None
        cleaned["department_position"] = None
        cleaned["department"] = None

        if target_type == "person":
            if not person:
                raise ValidationError("Select a person.")
            cleaned["person"] = person

            
            cleaned["department"] = (person.department or "").strip() or None

        elif target_type == "desk":
            if not desk:
                raise ValidationError("Select a desk.")
            if not department_position:
                raise ValidationError({"department_position": "Select a department position."})
            if office and desk.room.office_id != office.id:
                raise ValidationError({"desk": "Selected desk is not in the chosen office."})
            if department_position.department.office_id != desk.room.office_id:
                raise ValidationError({"department_position": "Selected department is not in the desk office."})
            if not _is_department_position_available(department_position):
                raise ValidationError({"department_position": "Selected department position is already assigned."})
            cleaned["desk"] = desk
            cleaned["department_position"] = department_position
            cleaned["department"] = str(department_position)

        elif target_type == "office":
            if not office:
                raise ValidationError("Select an office.")
            cleaned["office"] = office

        elif target_type == "department":
            if not department_position:
                raise ValidationError("Select a department position.")
            if office and department_position.department.office_id != office.id:
                raise ValidationError({"department_position": "Selected department is not in the chosen office."})
            if not _is_department_position_available(department_position):
                raise ValidationError({"department_position": "Selected department position is already assigned."})
            cleaned["department_position"] = department_position
            cleaned["department"] = str(department_position)

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
        fields = ["asset", "office", "department_position", "loan_date", "due_date"]
        widgets = {
            "loan_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["office"].queryset = Office.objects.order_by("name")

        _configure_department_position_field(self)

        self.fields["office"].required = True
        self.fields["department_position"].required = True

        _bootstrapify(self)
        _configure_loan_date_fields(self, company_due_default=True)

    def clean(self):
        cleaned = super().clean()
        asset = cleaned.get("asset")
        office = cleaned.get("office")
        department_position = cleaned.get("department_position")

        if not asset:
            raise ValidationError("Asset is required.")
        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

        if not office:
            raise ValidationError("Office is required.")
        if not department_position:
            raise ValidationError("Department is required.")
        if department_position.department.office_id != office.id:
            raise ValidationError({"department_position": "Selected department is not in the chosen office."})
        if not _is_department_position_available(department_position):
            raise ValidationError({"department_position": "Selected department position is already assigned."})

        cleaned["department"] = str(department_position)

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

        self.fields["asset"].queryset = Asset.objects.filter(status="available").order_by("name")
        self.fields["office"].queryset = Office.objects.order_by("name")

        desks_qs = Desk.objects.select_related("room__office").order_by(
            "room__office__name", "room__name", "code"
        )
        self.fields["desk"].queryset = desks_qs
        self.fields["desk"].widget = DeskByOfficeSelect(
            desk_office_map={str(desk.pk): desk.room.office_id for desk in desks_qs}
        )
        self.fields["desk"].widget.choices = self.fields["desk"].choices

        _configure_department_position_field(self)

        self.fields["office"].required = True
        self.fields["department_position"].required = True
        self.fields["desk"].required = True

        _bootstrapify(self)
        _configure_loan_date_fields(self)

    class Meta:
        model = Loan
        fields = ["asset", "office", "department_position", "desk", "loan_date", "due_date"]
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
        asset = cleaned.get("asset")
        office = cleaned.get("office")
        desk = cleaned.get("desk")
        department_position = cleaned.get("department_position")

        if not asset:
            raise ValidationError("Asset is required.")
        if asset.status != "available":
            raise ValidationError("Selected asset is not available.")

        if not office:
            raise ValidationError("Office is required.")
        if not department_position:
            raise ValidationError("Department is required.")
        if department_position.department.office_id != office.id:
            raise ValidationError({"department_position": "Selected department is not in the chosen office."})
        if not _is_department_position_available(department_position):
            raise ValidationError({"department_position": "Selected department position is already assigned."})

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
        cleaned["department"] = str(department_position)
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
