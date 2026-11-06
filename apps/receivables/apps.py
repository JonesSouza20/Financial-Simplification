from django.apps import AppConfig


class ReceivablesConfig(AppConfig):
    name = "apps.receivables"
    label = "receivables"
    verbose_name = "Valores a receber"

    def ready(self) -> None:
        from . import signals  # noqa: F401
