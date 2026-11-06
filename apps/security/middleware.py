"""Expiração de sessão por inatividade e absoluta (security-plan.md §3.2)."""

import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from . import devices

SKIP_PREFIXES = ("/static/", "/manifest.webmanifest", "/sw.js")


class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(SKIP_PREFIXES):
            now = int(time.time())
            last = request.session.get("last_activity", now)
            started = request.session.get("auth_started", now)
            idle = now - last > settings.FINANCAS_SESSION_IDLE_SECONDS
            absolute = now - started > settings.FINANCAS_SESSION_ABSOLUTE_SECONDS
            if idle or absolute:
                logout(request)
                target = "security:pin" if devices.find(request) else "security:login"
                url = f"{reverse(target)}?{urlencode({'next': request.get_full_path()})}"
                if request.headers.get("HX-Request"):
                    return HttpResponse(status=204, headers={"HX-Redirect": url})
                return redirect(url)
            request.session["last_activity"] = now
        return self.get_response(request)
