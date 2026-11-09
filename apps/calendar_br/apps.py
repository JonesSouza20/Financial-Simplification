from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed(sender, **kwargs):
    from .services import seed

    seed()


class CalendarBrConfig(AppConfig):
    name = "apps.calendar_br"
    label = "calendar_br"
    verbose_name = "Calendário de dias úteis"

    def ready(self) -> None:
        # Carga idempotente após migrate e após o flush dos testes. Só preenche anos sem
        # nenhum feriado, para não desfazer edições do usuário (RN-092).
        post_migrate.connect(_seed, sender=self)
