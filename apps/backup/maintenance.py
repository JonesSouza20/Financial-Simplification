"""Bloqueio de manutenção durante a restauração sobre o banco em uso (security-plan.md §7.2,
passo 6). Enquanto ativo, as outras requisições recebem 503 e o agendador não roda tarefas.
Vale para o processo único do sistema (ADR-011)."""

from __future__ import annotations

import threading
from contextlib import contextmanager

from django.http import HttpResponse

_lock = threading.Lock()
_active = threading.Event()


def active() -> bool:
    return _active.is_set()


@contextmanager
def gate():
    from .core import BackupError

    if not _lock.acquire(blocking=False):
        raise BackupError("Já existe uma restauração em andamento.")
    _active.set()
    try:
        yield
    finally:
        _active.clear()
        _lock.release()


PAGE = (
    "<!doctype html><meta charset='utf-8'><title>Restaurando</title>"
    "<p>Restaurando um backup. Tente de novo em alguns segundos.</p>"
)


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if active():
            response = HttpResponse(PAGE, status=503)
            response["Retry-After"] = "30"
            return response
        return self.get_response(request)
