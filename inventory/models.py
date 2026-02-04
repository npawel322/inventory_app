from django.db import models
from django.conf import settings
from django.utils import timezone


class Office(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True, null=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    COLOR_CHOICES = [
        ("yellow", "Yellow"),
        ("blue", "Blue"),
        ("green", "Green"),
        ("purple", "Purple"),
        ("orange", "Orange"),
    ]

    office = models.ForeignKey(Office, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["office", "name"], name="uniq_department_office_name")
        ]
        ordering = ["office__name", "name"]

    def __str__(self):
        return f"{self.office.name} / {self.name}"


class DepartmentPosition(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="positions")
    number = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["department", "number"], name="uniq_department_position")
        ]
        ordering = ["department__office__name", "department__name", "number"]

    def __str__(self):
        return f"{self.department.name} #{self.number}"


class Room(models.Model):
    office = models.ForeignKey(Office, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50, default="open_space")

    def __str__(self):
        return f"{self.office.name} / {self.name}"


class Desk(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="desks")
    code = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["room", "code"], name="uniq_desk_room_code")
        ]

    def __str__(self):
        return f"{self.room.office.name} / {self.room.name} / {self.code}"


class AssetCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Asset(models.Model):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("assigned", "Assigned"),
        ("in_service", "In service"),
        ("retired", "Retired"),
    ]

    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets")
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=120, unique=True)
    asset_tag = models.CharField(max_length=120, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    purchase_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"


class Person(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    department = models.CharField(max_length=120, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="person_profile",
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Loan(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="loans")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_loans",
    )


    # target: exactly one of the following
    person = models.ForeignKey(Person, on_delete=models.PROTECT, blank=True, null=True, related_name="loans")
    desk = models.ForeignKey(Desk, on_delete=models.PROTECT, blank=True, null=True, related_name="loans")
    office = models.ForeignKey(Office, on_delete=models.PROTECT, blank=True, null=True, related_name="loans")
    department_position = models.ForeignKey(
        DepartmentPosition,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="loans",
    )
    department = models.CharField(max_length=120, blank=True, null=True)

    loan_date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    return_date = models.DateField(blank=True, null=True)
    issued_by = models.CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f"Loan #{self.id} - {self.asset}"

    @property
    def is_active(self) -> bool:
        return self.return_date is None

    @property
    def office_label(self) -> str:
        if self.office:
            return str(self.office)
        if self.desk:
            return str(self.desk.room.office)
        if self.department_position:
            return str(self.department_position.department.office)
        return "-"

    @property
    def desk_label(self) -> str:
        if self.desk:
            return str(self.desk)
        return "-"

    @property
    def department_label(self) -> str:
        if self.department_position:
            return str(self.department_position)
        if self.department:
            return self.department
        return "-"

    def target_label(self) -> str:
        if self.person:
            return f"Person: {self.person}"
        if self.desk:
            return f"Desk: {self.desk}"
        if self.office:
            return f"Office: {self.office}"
        if self.department_position:
            return f"Department: {self.department_position}"
        if self.department:
            return f"Department: {self.department}"
        return "-"
