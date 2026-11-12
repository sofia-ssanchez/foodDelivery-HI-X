"""Separate development login cookies for each trusted localhost frontend.

Browsers do not scope cookies by port. Select a distinct HttpOnly token pair
using the browser-supplied Origin instead. This is development session isolation,
not a security boundary between mutually untrusted applications on localhost.
"""
from hashlib import sha256
from urllib.parse import urlsplit

from django.conf import settings


def auth_cookie_name(request, token_type):
    base = f"{token_type}_token"
    origin = request.headers.get("Origin", "")
    if not settings.DEBUG or origin not in settings.CORS_ALLOWED_ORIGINS:
        return base
    if urlsplit(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
        return base
    scope = sha256(origin.encode()).hexdigest()[:16]
    return f"{base}_local_{scope}"
