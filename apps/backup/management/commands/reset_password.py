"""Redefine a senha de login no próprio PC (security-plan.md §10.4).

Pede a senha de backup como prova adicional. Revoga todos os aparelhos confiáveis.
"""

import getpass
import hmac

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.backup import secrets
from apps.ledger import audit
from apps.security import devices
from apps.security.views import USERNAME


class Command(BaseCommand):
    help = "Redefine a senha de login (exige a senha de backup)."

    def handle(self, *args, **options):
        stored = secrets.get(secrets.BACKUP_PASSPHRASE)
        if not stored:
            raise CommandError("Senha de backup não configurada: redefinição bloqueada.")
        if not hmac.compare_digest(getpass.getpass("Senha de backup: "), stored):
            raise CommandError("Senha de backup incorreta.")
        user = get_user_model().objects.filter(username=USERNAME).first()
        if user is None:
            raise CommandError("Nenhum usuário. Abra o sistema e crie a senha.")
        new = getpass.getpass("Nova senha de login: ")
        if new != getpass.getpass("Repita a nova senha: "):
            raise CommandError("As senhas não são iguais.")
        try:
            password_validation.validate_password(new, user)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        user.set_password(new)
        user.save()
        devices.revoke_all(user, reason="redefinição de senha no PC")
        audit.record_event("password_reset", "auth_user", user.pk)
        self.stdout.write("Senha redefinida. Aparelhos confiáveis revogados.")
