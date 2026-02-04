from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import (
    Department,
    DepartmentPosition,
    Office, Room, Desk,
    AssetCategory, Asset,
    Person, Loan
)

from faker import Faker
import random
from datetime import timedelta


class Command(BaseCommand):
    help = "Seed inventory database with realistic demo data"

    def handle(self, *args, **options):
        fake = Faker("en_US")

        self.stdout.write("Seeding database with realistic data...")

        # ---------- CLEAR DATABASE ----------
        Loan.objects.all().delete()
        Desk.objects.all().delete()
        Room.objects.all().delete()
        Office.objects.all().delete()
        DepartmentPosition.objects.all().delete()
        Department.objects.all().delete()
        Asset.objects.all().delete()
        AssetCategory.objects.all().delete()
        Person.objects.all().delete()

        # ---------- OFFICES ----------
        offices = []
        for city in ["New York", "London", "Berlin", "Warsaw", "Amsterdam"]:
            offices.append(
                Office.objects.create(
                    name=f"{city} Office",
                    address=fake.address()
                )
            )

        # ---------- ROOMS ----------
        rooms = []
        for office in offices:
            for i in range(1, 5):
                rooms.append(
                    Room.objects.create(
                        office=office,
                        name=f"Room {i}",
                        type=random.choice(["open_space", "meeting", "private"])
                    )
                )

        # ---------- DEPARTMENTS ----------
        dept_defs = [
            ("Yellow", "yellow"),
            ("Blue", "blue"),
            ("Green", "green"),
            ("Purple", "purple"),
            ("Orange", "orange"),
        ]
        positions = []
        for office in offices:
            for dep_name, dep_color in dept_defs:
                dep = Department.objects.create(
                    office=office,
                    name=dep_name,
                    color=dep_color,
                )
                for idx in range(1, 11):
                    positions.append(
                        DepartmentPosition.objects.create(
                            department=dep,
                            number=idx,
                        )
                    )

        # ---------- DESKS ----------
        desks = []
        for room in rooms:
            for i in range(1, 6):
                desks.append(
                    Desk.objects.create(
                        room=room,
                        code=f"DESK-{i}"
                    )
                )

        # ---------- ASSET CATEGORIES ----------
        categories = {
            "Laptop": [
                "Dell Latitude 5420",
                "Lenovo ThinkPad T14",
                "HP EliteBook 840",
                "MacBook Pro 14",
            ],
            "Monitor": [
                "Dell P2419H",
                "LG UltraFine 27",
                "Samsung Odyssey G5",
            ],
            "Phone": [
                "iPhone 12",
                "Samsung Galaxy S21",
                "Google Pixel 6",
            ],
            "Accessories": [
                "Logitech MX Master 3 Mouse",
                "Logitech MX Keys Keyboard",
                "Jabra Evolve 65 Headset",
                "Dell WD19 Docking Station",
            ],
        }

        category_objs = {}
        for cat_name in categories.keys():
            category_objs[cat_name] = AssetCategory.objects.create(name=cat_name)

        # ---------- ASSETS (25) ----------
        assets = []
        serial_counter = 10000

        for cat_name, models in categories.items():
            for model in models:
                for _ in range(2):  # kilka sztuk każdego
                    serial_counter += 1
                    assets.append(
                        Asset.objects.create(
                            category=category_objs[cat_name],
                            name=model,
                            serial_number=f"SN-{serial_counter}",
                            asset_tag=f"AST-{serial_counter}",
                            status="available",
                            notes="Company owned equipment"
                        )
                    )

        # ---------- PERSONS (20) ----------
        departments = ["IT", "HR", "Finance", "Operations", "Admin"]
        persons = []

        for _ in range(20):
            first = fake.first_name()
            last = fake.last_name()
            email = f"{first[0].lower()}{last.lower()}{random.randint(1000,9999)}@outlook.com"

            persons.append(
                Person.objects.create(
                    first_name=first,
                    last_name=last,
                    department=random.choice(departments),
                    email=email
                )
            )

        # ---------- LOANS (15) ----------
        available_assets = assets.copy()

        for _ in range(15):
            asset = random.choice(available_assets)
            available_assets.remove(asset)

            loan_date = timezone.now().date() - timedelta(days=random.randint(1, 20))
            due_date = loan_date + timedelta(days=random.randint(7, 30))

            loan = Loan.objects.create(
                asset=asset,
                loan_date=loan_date,
                due_date=due_date,
                issued_by="IT Department"
            )

            target_type = random.choice(["person", "desk", "office", "department"])

            if target_type == "person":
                loan.person = random.choice(persons)
            elif target_type == "desk":
                loan.desk = random.choice(desks)
            elif target_type == "office":
                loan.office = random.choice(offices)
            else:
                position = random.choice(positions)
                loan.department_position = position
                loan.department = str(position)

            loan.save()

            asset.status = "assigned"
            asset.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS("✔ Database seeded with realistic data!"))
