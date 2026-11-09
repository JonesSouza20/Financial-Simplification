"""Envio pelo bot do Telegram. O bot só envia, para um único chat (security-plan.md §6).

O token faz parte da URL da API, então qualquer erro pode carregá-lo. Toda mensagem de erro
sai daqui limpa, e sem encadear a exceção original, que iria parar no log.
"""

from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from apps.backup import secrets
from apps.ui import models as prefs

CHAT_KEY = "telegram_chat_id"
API = "https://api.telegram.org/bot{token}/sendMessage"
TOKEN_RE = re.compile(r"\d{5,}:[\w-]{20,}")
TIMEOUT_SECONDS = 10
HTTP_REASONS = {
    400: "O Telegram não encontrou esse chat. Confira o número do chat.",
    401: "O Telegram recusou o token. Confira ou gere outro.",
    403: "O bot não pode falar nesse chat. Envie /start para ele primeiro.",
    429: "O Telegram pediu para esperar um pouco antes de enviar mais.",
}


class TelegramError(Exception):
    """Falha ao enviar. A mensagem já vem sem o token."""


def scrub(text, token: str | None = None) -> str:
    text = str(text)
    if token:
        text = text.replace(token, "***")
    return TOKEN_RE.sub("***", text)


def configured() -> bool:
    return secrets.has(secrets.TELEGRAM_TOKEN) and bool(prefs.get(CHAT_KEY))


def send(text: str) -> None:
    token = secrets.get(secrets.TELEGRAM_TOKEN)
    chat_id = prefs.get(CHAT_KEY)
    if not token or not chat_id:
        raise TelegramError("O Telegram ainda não foi configurado.")
    body = urlencode({"chat_id": chat_id, "text": text}).encode()
    request = Request(API.format(token=token), data=body, method="POST")  # noqa: S310 - URL fixa
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS):  # noqa: S310 - URL fixa, sempre https
            return
    except HTTPError as exc:
        reason = HTTP_REASONS.get(exc.code, f"O Telegram respondeu com erro {exc.code}.")
    except (URLError, OSError) as exc:
        detail = getattr(exc, "reason", exc)
        reason = f"Sem conexão com o Telegram: {scrub(detail, token)}"
    raise TelegramError(scrub(reason, token)) from None
