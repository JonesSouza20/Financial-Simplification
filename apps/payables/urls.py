from django.urls import path

from . import views

app_name = "payables"

urlpatterns = [
    path("pagamentos/", views.central, name="central"),
    path("pagamentos/nova/", views.new_bill, name="new_bill"),
    path("pagamentos/receita/", views.new_income, name="new_income"),
    path("pagamentos/calendario/", views.calendar_view, name="calendar"),
    path("pagamentos/recorrencias/", views.recurrences, name="recurrences"),
    path("pagamentos/recorrencias/nova/", views.recurrence_new, name="recurrence_new"),
    path(
        "pagamentos/recorrencias/<int:pk>/alterar/", views.recurrence_edit, name="recurrence_edit"
    ),
    path("pagamentos/recorrencias/<int:pk>/encerrar/", views.recurrence_end, name="recurrence_end"),
    path("pagamentos/<int:pk>/pagar/", views.pay, name="pay"),
    path("pagamentos/<int:pk>/pronto/", views.done, name="done"),
    path("pagamentos/<int:pk>/valor/", views.actual, name="actual"),
    path("pagamentos/<int:pk>/agendar/", views.schedule, name="schedule"),
    path("pagamentos/<int:pk>/desagendar/", views.unschedule, name="unschedule"),
    path("pagamentos/<int:pk>/cancelar/", views.cancel, name="cancel"),
    path("pagamentos/<int:pk>/encerrar/", views.close, name="close"),
    path("ajustes/dinheiro/", views.money_settings, name="money_settings"),
    path("ajustes/feriados/", views.holidays, name="holidays"),
    path("ajustes/feriados/<str:day>/remover/", views.holiday_remove, name="holiday_remove"),
]
