from django.urls import path

from . import views

app_name = "debts"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nova-divida/", views.create_loan, name="create_loan"),
    path("novo-consorcio/", views.create_consortium, name="create_consortium"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/pagar/", views.pay, name="pay"),
]
