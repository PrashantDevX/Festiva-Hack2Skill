from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time

SESSION_COOKIE = "festiva_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
_DEV_SECRET = b"festiva-local-development-session-secret-change-before-production"
_CLOCK_SKEW_SECONDS = 60
_MAX_TOKEN_LENGTH = 512


class SessionConfigError(RuntimeError):
    """Raised when production session configuration is missing or unsafe."""


def _session_secret() -> bytes:
    configured = os.getenv("FESTIVA_SESSION_SECRET", "").strip()
    if configured:
        if len(configured) < 32:
            raise SessionConfigError(
                "FESTIVA_SESSION_SECRET must be at least 32 characters."
            )
        return configured.encode("utf-8")
    if os.getenv("VERCEL"):
        raise SessionConfigError(
            "FESTIVA_SESSION_SECRET must be set in production."
        )
    # Local development and tests only. Production refuses to use this value.
    return _DEV_SECRET


def session_configured() -> bool:
    try:
        _session_secret()
    except SessionConfigError:
        return False
    return True


def _signature(owner_id: str, issued_at: int, secret: bytes) -> str:
    payload = f"{owner_id}.{issued_at}".encode("ascii")
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def issue_session() -> tuple[str, str]:
    """Create an anonymous owner ID and its signed cookie value."""
    owner_id = secrets.token_urlsafe(32)
    issued_at = int(time.time())
    token = (
        f"{owner_id}.{issued_at}."
        f"{_signature(owner_id, issued_at, _session_secret())}"
    )
    return owner_id, token


def validate_session(token: str | None) -> str | None:
    """Return the owner ID only when the signed session is authentic and fresh."""
    if not token or len(token) > _MAX_TOKEN_LENGTH:
        return None
    try:
        owner_id, issued_raw, signature = token.split(".")
        issued_at = int(issued_raw)
    except (ValueError, TypeError):
        return None
    if not _OWNER_PATTERN.fullmatch(owner_id):
        return None
    now = int(time.time())
    if issued_at > now + _CLOCK_SKEW_SECONDS:
        return None
    if now - issued_at > SESSION_MAX_AGE_SECONDS:
        return None
    try:
        expected = _signature(owner_id, issued_at, _session_secret())
    except SessionConfigError:
        return None
    if not hmac.compare_digest(signature, expected):
        return None
    return owner_id
