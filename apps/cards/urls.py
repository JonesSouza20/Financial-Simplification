from django.urls import path

from . import views

app_name = "cards"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("novo/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/pagar/", views.pay, name="pay"),
    path("<int:pk>/aparencia/", views.appearance, name="appearance"),
    path("<int:pk>/item-de-abertura/", views.add_opening_item, name="add_opening_item"),
]
