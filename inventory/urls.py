from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth
    path("login/", views.RoleBasedLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("", views.home, name="home"),

    path("assets/", views.assets_list, name="assets_list"),
    path("assets/new/", views.asset_create, name="asset_create"),

    path("persons/", views.persons_list, name="persons_list"),
    path("persons/new/", views.person_create, name="person_create"),

    path("loans/", views.loans_list, name="loans_list"),
    path("loans/new/", views.loan_create, name="loan_create"),
    path("loans/<int:loan_id>/return/", views.loan_return, name="loan_return"),

    path("history/", views.history, name="history"),
]
