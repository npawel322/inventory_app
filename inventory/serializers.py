from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Asset, AssetCategory, Desk, Loan, Office, Person, Room


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ["id", "name"]


class AssetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "serial_number",
            "asset_tag",
            "status",
            "purchase_date",
            "notes",
        ]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "first_name", "last_name", "department", "email"]


class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Office
        fields = ["id", "name", "address"]


class RoomSerializer(serializers.ModelSerializer):
    office_name = serializers.CharField(source="office.name", read_only=True)

    class Meta:
        model = Room
        fields = ["id", "office", "office_name", "name", "type"]


class DeskSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="room.name", read_only=True)
    office_name = serializers.CharField(source="room.office.name", read_only=True)

    class Meta:
        model = Desk
        fields = ["id", "room", "room_name", "office_name", "code"]


class LoanSerializer(serializers.ModelSerializer):
    asset_label = serializers.CharField(source="asset.__str__", read_only=True)
    department_position_label = serializers.CharField(source="department_position.__str__", read_only=True)
    target = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "asset",
            "asset_label",
            "person",
            "desk",
            "office",
            "department_position",
            "department_position_label",
            "department",
            "loan_date",
            "due_date",
            "return_date",
            "issued_by",
            "target",
        ]
        read_only_fields = ["loan_date", "return_date", "target", "asset_label", "department_position_label"]

    def get_target(self, obj: Loan):
        if obj.person:
            return {"type": "person", "label": str(obj.person)}
        if obj.desk:
            return {"type": "desk", "label": str(obj.desk)}
        if obj.office:
            return {"type": "office", "label": str(obj.office)}
        if obj.department_position:
            return {"type": "department", "label": str(obj.department_position)}
        if obj.department:
            return {"type": "department", "label": obj.department}
        return {"type": None, "label": "-"}

    def validate(self, attrs):
        asset = attrs.get("asset")
        person = attrs.get("person")
        desk = attrs.get("desk")
        office = attrs.get("office")
        department_position = attrs.get("department_position")
        department = (attrs.get("department") or "").strip()

        if not asset:
            raise serializers.ValidationError({"asset": "Asset is required."})
        if asset.status != "available":
            raise serializers.ValidationError({"asset": "Asset is not available."})

        targets = [
            ("person", person),
            ("desk", desk),
            ("office", office),
            ("department_position", department_position),
            ("department", department if department else None),
        ]
        chosen = [(key, value) for key, value in targets if value]
        if len(chosen) != 1:
            raise serializers.ValidationError(
                "Choose exactly one target: person OR desk OR office OR department."
            )

        if department_position and department_position.loans.filter(return_date__isnull=True).exists():
            raise serializers.ValidationError(
                {"department_position": "Selected department position is already assigned."}
            )

        if department:
            attrs["department"] = department
        elif department_position:
            attrs["department"] = str(department_position)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        asset = validated_data["asset"]
        asset.status = "assigned"
        asset.save(update_fields=["status"])

        loan = Loan.objects.create(
            **validated_data,
            loan_date=timezone.now().date(),
        )
        return loan
