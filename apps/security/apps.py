from django.apps import AppConfig


class SecurityConfig(AppConfig):
    name = "apps.security"
    label = "security"
    verbose_name = "Segurança"

    def ready(self) -> None:
        from . import signals  # noqa: F401
