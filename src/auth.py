"""Hosted identity settings and the token-verifier interface.

A real identity-provider tenant is out of scope. Tests inject a fake
verifier. Hosted mode still refuses to start when an OIDC variable is
missing, so the service cannot come up open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

ROLES = ("analyst", "admin", "auditor")
_REQUIRED = (
    "VIRTUTRIAL_OIDC_ISSUER",
    "VIRTUTRIAL_OIDC_CLIENT_ID",
    "VIRTUTRIAL_OIDC_CLIENT_SECRET",
)


@dataclass(frozen=True)
class Actor:
    """Verified caller. ``role`` is one of analyst, admin, auditor."""

    subject: str
    role: str

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError("role must be analyst, admin, or auditor.")


@dataclass(frozen=True)
class HostedSettings:
    """OIDC settings loaded from the environment. The secret stays in memory."""

    issuer: str
    client_id: str
    client_secret: str


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Actor:
        """Return the actor for a bearer token, or raise."""


class RejectAllVerifier:
    """Production default until a tenant-specific verifier is wired."""

    def verify(self, token: str) -> Actor:
        raise PermissionError("No token verifier is configured.")


class StaticTokenVerifier:
    """Map of token string to actor. For tests only."""

    def __init__(self, actors: Mapping[str, Actor]) -> None:
        self._actors = dict(actors)

    def verify(self, token: str) -> Actor:
        if token not in self._actors:
            raise PermissionError("Unknown token.")
        return self._actors[token]


def load_hosted_settings(env: Mapping[str, str]) -> HostedSettings:
    """Raise RuntimeError when a required OIDC variable is missing."""

    missing = [name for name in _REQUIRED if not str(env.get(name, "")).strip()]
    if missing:
        raise RuntimeError(
            "Hosted mode needs these environment variables: " + ", ".join(missing) + "."
        )
    return HostedSettings(
        issuer=str(env["VIRTUTRIAL_OIDC_ISSUER"]).strip(),
        client_id=str(env["VIRTUTRIAL_OIDC_CLIENT_ID"]).strip(),
        client_secret=str(env["VIRTUTRIAL_OIDC_CLIENT_SECRET"]).strip(),
    )


def parse_mode(value: str | None) -> str:
    """Return ``local`` or ``hosted``. Anything else is refused."""

    mode = (value or "local").strip().lower()
    if mode not in {"local", "hosted"}:
        raise RuntimeError("VIRTUTRIAL_MODE must be local or hosted.")
    return mode
