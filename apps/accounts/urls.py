from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nova/", views.create, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/arquivar/", views.archive, name="archive"),
]
