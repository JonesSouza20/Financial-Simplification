from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("avisos/", views.alert_settings, name="settings"),
    path("avisos/teste/", views.send_test, name="test"),
]
