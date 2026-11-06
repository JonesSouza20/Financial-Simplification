from django.apps import AppConfig


def _on_created(sender, transaction, **kwargs):
    from .reconciliation import mark_stale

    mark_stale(transaction)


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Contas financeiras"

    def ready(self) -> None:
        from apps.ledger.signals import transaction_created

        # Lançamento em período já conciliado deixa o marco "a reconciliar" (RN-133).
        transaction_created.connect(_on_created, dispatch_uid="accounts.mark_stale")
