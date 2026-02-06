from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views

from .models import Asset, Person, Loan
from .forms import AssetForm, PersonForm, AdminLoanForm, CompanyLoanForm, EmployeeLoanForm
from .roles import get_user_role, role_required, ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_COMPANY
from .filters import AssetFilter
from .filters import PersonFilter



class RoleBasedLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        role = get_user_role(self.request.user)
        if role == ROLE_ADMIN:
            return reverse("assets_list")
        return reverse("loans_list")


@login_required
def home(request):
    role = get_user_role(request.user)
    if role == ROLE_ADMIN:
        return redirect("assets_list")
    return redirect("loans_list")


@login_required
@role_required(ROLE_ADMIN)
def assets_list(request):
    assets = Asset.objects.select_related("category").order_by("-id")
    f = AssetFilter(request.GET, queryset=assets)
    return render(request, "inventory/assets_list.html", {"assets": f.qs, "filter": f})


@login_required
@role_required(ROLE_ADMIN)
def asset_create(request):
    if request.method == "POST":
        form = AssetForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("assets_list")
    else:
        form = AssetForm()
    return render(request, "inventory/form.html", {"title": "Add asset", "form": form, "cancel_url": "assets_list"})


@login_required
@role_required(ROLE_ADMIN)
def persons_list(request):
    persons = Person.objects.order_by("last_name", "first_name")
    f = PersonFilter(request.GET, queryset=persons)
    return render(request, "inventory/persons_list.html", {"persons": f.qs, "filter": f})


@login_required
@role_required(ROLE_ADMIN)
def person_create(request):
    if request.method == "POST":
        form = PersonForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("persons_list")
    else:
        form = PersonForm()
    return render(request, "inventory/form.html", {"title": "Add person", "form": form})


def _resolve_person_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    # explicit link
    try:
        return user.person_profile
    except Exception:
        pass
    # fallback by email
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return Person.objects.filter(email__iexact=email).first()
    return None


@login_required
def loans_list(request):
    role = get_user_role(request.user)
    base_qs = Loan.objects.select_related(
        "asset", "person", "desk__room__office", "office", "created_by"
    ).filter(return_date__isnull=True)

    person = _resolve_person_for_user(request.user)

    if role == ROLE_ADMIN:
        loans = base_qs
    else:
        q = Q(created_by=request.user)
        if person:
            q |= Q(person=person)
        loans = base_qs.filter(q)

    sort_field = request.GET.get("sort") or "issue"
    sort_dir = request.GET.get("dir") or "desc"
    sort_map = {"issue": "loan_date", "due": "due_date"}
    sort_attr = sort_map.get(sort_field, "loan_date")
    prefix = "" if sort_dir == "asc" else "-"
    loans = loans.order_by(f"{prefix}{sort_attr}", "-id")

    is_admin = role == ROLE_ADMIN
    return render(
        request,
        "inventory/loans_list.html",
        {
            "loans": loans,
            "today": timezone.now().date(),
            "is_admin": is_admin,
            "role": role,
            'cancel_url': 'loans_list',
            "sort_field": sort_field,
            "sort_dir": sort_dir,
        },
    )


@login_required
@transaction.atomic
def loan_create(request):
    role = get_user_role(request.user)

    if role == ROLE_ADMIN:
        FormCls = AdminLoanForm
        form_kwargs = {}
    elif role == ROLE_COMPANY:
        FormCls = CompanyLoanForm
        form_kwargs = {}
    else:
        FormCls = EmployeeLoanForm
        form_kwargs = {"user": request.user}

    if request.method == "POST":
        form = FormCls(request.POST, **form_kwargs)
        if form.is_valid():
            loan = form.save(commit=False)

            # meta
            loan.created_by = request.user
            loan.issued_by = request.user.username

            # lock asset + set status
            asset = loan.asset
            asset.status = "assigned"
            asset.save(update_fields=["status"])

            loan.save()
            return redirect("loans_list")
    else:
        form = FormCls(**form_kwargs)

    return render(
        request,
        "inventory/loan_form.html",
        {
            "form": form,
            "role": role,
            "person": _resolve_person_for_user(request.user),
        },
    )


@login_required
@transaction.atomic
def loan_return(request, loan_id: int):
    if request.method != "POST":
        # protect against GET returns
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    loan = get_object_or_404(Loan, pk=loan_id)
    role = get_user_role(request.user)
    is_admin = role == ROLE_ADMIN

    # non-admin can only return their own loans
    allowed = is_admin
    if not allowed:
        if loan.created_by_id == request.user.id:
            allowed = True
        elif loan.person and getattr(loan.person, "user_id", None) == request.user.id:
            allowed = True

    if not allowed:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You cannot return this loan.")

    if loan.return_date is None:
        loan.return_date = timezone.now().date()
        loan.save(update_fields=["return_date"])

        asset = loan.asset
        asset.status = "available"
        asset.save(update_fields=["status"])

    return redirect("loans_list")


@login_required
def history(request):
    role = get_user_role(request.user)
    base_qs = Loan.objects.select_related(
        "asset", "person", "desk__room__office", "office", "created_by"
    )

    person = _resolve_person_for_user(request.user)

    if role == ROLE_ADMIN:
        loans = base_qs
    else:
        q = Q(created_by=request.user)
        if person:
            q |= Q(person=person)
        loans = base_qs.filter(q)

    sort_field = request.GET.get("sort") or "issue"
    sort_dir = request.GET.get("dir") or "desc"
    sort_map = {"issue": "loan_date", "due": "due_date"}
    sort_attr = sort_map.get(sort_field, "loan_date")
    prefix = "" if sort_dir == "asc" else "-"
    loans = loans.order_by(f"{prefix}{sort_attr}", "-id")

    return render(
        request,
        "inventory/history.html",
        {
            "loans": loans,
            "today": timezone.now().date(),
            "role": role,
            "is_admin": role == ROLE_ADMIN,
            "sort_field": sort_field,
            "sort_dir": sort_dir,
        },
    )
