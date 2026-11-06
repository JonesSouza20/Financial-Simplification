from django.apps import AppConfig


class CardsConfig(AppConfig):
    name = "apps.cards"
    label = "cards"
    verbose_name = "Cartões"

    def ready(self) -> None:
        from . import signals  # noqa: F401
