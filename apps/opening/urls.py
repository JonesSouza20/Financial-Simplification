from django.urls import path

from . import views

app_name = "opening"

urlpatterns = [
    path("<slug:step>/", views.step, name="step"),
]
