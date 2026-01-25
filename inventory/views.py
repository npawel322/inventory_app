from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from .models import Asset, Person, Loan
from .forms import AssetForm, PersonForm, LoanForm


def assets_list(request):
    assets = Asset.objects.select_related("category").order_by("-id")
    return render(request, "inventory/assets_list.html", {"assets": assets})


def asset_create(request):
    if request.method == "POST":
        form = AssetForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("assets_list")
    else:
        form = AssetForm()
    return render(request, "inventory/form.html", {"title": "Add asset", "form": form})


def persons_list(request):
    persons = Person.objects.order_by("last_name", "first_name")
    return render(request, "inventory/persons_list.html", {"persons": persons})


def person_create(request):
    if request.method == "POST":
        form = PersonForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("persons_list")
    else:
        form = PersonForm()
    return render(request, "inventory/form.html", {"title": "Add person", "form": form})


def loans_list(request):
    loans = Loan.objects.select_related(
        "asset", "person", "desk__room__office", "office"
    ).filter(return_date__isnull=True).order_by("-id")
    return render(request, "inventory/loans_list.html", {"loans": loans, "today": timezone.now().date()})


@transaction.atomic
def loan_create(request):
    if request.method == "POST":
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)

            # lock asset + set status
            asset = loan.asset
            asset.status = "assigned"
            asset.save(update_fields=["status"])

            loan.save()
            return redirect("loans_list")
    else:
        form = LoanForm()
    return render(request, "inventory/loan_form.html", {"form": form})


@transaction.atomic
def loan_return(request, loan_id: int):
    loan = get_object_or_404(Loan, pk=loan_id)
    if loan.return_date is None:
        loan.return_date = timezone.now().date()
        loan.save(update_fields=["return_date"])

        asset = loan.asset
        asset.status = "available"
        asset.save(update_fields=["status"])

    return redirect("loans_list")


def history(request):
    loans = Loan.objects.select_related(
        "asset", "person", "desk__room__office", "office"
    ).order_by("-id")
    return render(request, "inventory/history.html", {"loans": loans, "today": timezone.now().date()})
