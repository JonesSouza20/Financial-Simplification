from django.urls import path

from . import views

app_name = "categories"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("<int:pk>/renomear/", views.rename, name="rename"),
    path("<int:pk>/arquivar/", views.archive, name="archive"),
]
