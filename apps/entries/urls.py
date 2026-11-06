from django.urls import path

from . import views

app_name = "entries"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("lancar/", views.quick, name="quick"),
    path("novo/", views.new, name="new"),
    path("desfazer/", views.undo, name="undo"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/corrigir/", views.correct, name="correct"),
    path("<int:pk>/estornar/", views.reverse, name="reverse"),
    path("<int:pk>/nota/", views.note, name="note"),
]
