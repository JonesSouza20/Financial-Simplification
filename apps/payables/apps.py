from django.apps import AppConfig


class PayablesConfig(AppConfig):
    name = "apps.payables"
    label = "payables"
    verbose_name = "Contas a pagar e receitas previstas"

    def ready(self) -> None:
        from . import signals  # noqa: F401 - conecta os receptores
