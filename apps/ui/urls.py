from django.urls import path

from . import views

app_name = "ui"

urlpatterns = [
    path("", views.home, name="home"),
    path("aparencia/", views.appearance, name="appearance"),
    path("mais/", views.more, name="more"),
    path("origem/<slug:slug>/", views.origin, name="origin"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
]
