from django.urls import path

from . import views

app_name = "backup"

urlpatterns = [
    path("", views.index, name="index"),
    path("senha/", views.set_passphrase, name="set_passphrase"),
    path("nuvem/", views.set_cloud, name="set_cloud"),
    path("agora/", views.backup_now, name="now"),
    path("testar/", views.test_restore, name="test"),
    path("restaurar/", views.restore, name="restore"),
    path("saude/", views.health_view, name="health"),
]
