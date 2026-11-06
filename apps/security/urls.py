from django.urls import path

from . import views

app_name = "security"

urlpatterns = [
    path("configurar/", views.setup, name="setup"),
    path("entrar/", views.login_view, name="login"),
    path("pin/", views.pin_view, name="pin"),
    path("sair/", views.logout_view, name="logout"),
    path("aparelhos/novo/", views.device_new, name="device_new"),
    path("seguranca/", views.settings_view, name="settings"),
    path("aparelhos/<int:pk>/revogar/", views.device_revoke, name="device_revoke"),
    path("aparelhos/revogar-todos/", views.device_revoke_all, name="device_revoke_all"),
    path("senha/", views.change_password, name="change_password"),
]
