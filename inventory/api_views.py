from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Asset, AssetCategory, Person, Office, Room, Desk, Loan
from .serializers import (
    AssetSerializer, AssetCategorySerializer, PersonSerializer,
    OfficeSerializer, RoomSerializer, DeskSerializer, LoanSerializer
)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    queryset = AssetCategory.objects.all().order_by("name")
    serializer_class = AssetCategorySerializer


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related("category").all().order_by("-id")
    serializer_class = AssetSerializer


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all().order_by("last_name", "first_name")
    serializer_class = PersonSerializer


class OfficeViewSet(viewsets.ModelViewSet):
    queryset = Office.objects.all().order_by("name")
    serializer_class = OfficeSerializer


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("office").all().order_by("office__name", "name")
    serializer_class = RoomSerializer


class DeskViewSet(viewsets.ModelViewSet):
    queryset = Desk.objects.select_related("room__office").all().order_by("room__office__name", "room__name", "code")
    serializer_class = DeskSerializer


class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.select_related(
        "asset", "person", "desk__room__office", "office"
    ).all().order_by("-id")
    serializer_class = LoanSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        active = self.request.query_params.get("active")
        if active == "1":
            qs = qs.filter(return_date__isnull=True)
        return qs

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def return_loan(self, request, pk=None):
        loan = get_object_or_404(Loan, pk=pk)

        if loan.return_date is not None:
            return Response({"detail": "Loan already returned."}, status=status.HTTP_400_BAD_REQUEST)

        loan.return_date = timezone.now().date()
        loan.save(update_fields=["return_date"])

        asset = loan.asset
        asset.status = "available"
        asset.save(update_fields=["status"])

        return Response(self.get_serializer(loan).data, status=status.HTTP_200_OK)
