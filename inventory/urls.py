from django.urls import path
from . import views

urlpatterns = [
    path("", views.assets_list, name="assets_list"),

    path("assets/", views.assets_list, name="assets_list"),
    path("assets/new/", views.asset_create, name="asset_create"),

    path("persons/", views.persons_list, name="persons_list"),
    path("persons/new/", views.person_create, name="person_create"),

    path("loans/", views.loans_list, name="loans_list"),
    path("loans/new/", views.loan_create, name="loan_create"),
    path("loans/<int:loan_id>/return/", views.loan_return, name="loan_return"),

    path("history/", views.history, name="history"),
]
