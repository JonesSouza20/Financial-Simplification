from django.urls import path

from . import views

app_name = "receivables"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/receber/", views.receive, name="receive"),
]
