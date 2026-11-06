"""Cabeçalhos de segurança (security-plan.md §8): CSP sem scripts externos nem inline."""

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "form-action 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ]
)

PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", PERMISSIONS)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            response.setdefault("Cache-Control", "no-store")
        return response
