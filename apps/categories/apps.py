from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed(sender, **kwargs):
    from .services import seed_defaults

    seed_defaults()


class CategoriesConfig(AppConfig):
    name = "apps.categories"
    label = "categories"
    verbose_name = "Categorias"

    def ready(self) -> None:
        # Carga idempotente da lista padrão após migrate e após flush dos testes.
        post_migrate.connect(_seed, sender=self)
