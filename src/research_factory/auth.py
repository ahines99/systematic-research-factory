"""API keys and roles (RSF-062, RSF-063, ADR-0004).

Keys look like ``rsf_<key_id>_<secret>``. Only a SHA-256 hash is stored (the secret is
256 bits of randomness, so a fast hash is appropriate). Keys are shown once, can be
revoked, and each belongs to exactly one role.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from enum import StrEnum

from .domain.clock import Clock
from .domain.errors import InvalidInputError
from .domain.identity import sha256_hex
from .persistence.repositories import ApiKeyRepository


class Role(StrEnum):
    GUEST = "guest"  # unauthenticated: read recorded demo runs and public data only
    VIEWER = "viewer"  # read everything
    RESEARCHER = "researcher"  # read, freeze experiments, run analyses and workflows
    APPROVER = "approver"  # read, record committee decisions


@dataclass(frozen=True)
class Principal:
    name: str
    role: Role
    key_id: str | None = None

    @property
    def is_guest(self) -> bool:
        return self.role is Role.GUEST


GUEST = Principal("guest", Role.GUEST)
LOCAL_OPERATOR = Principal("local-operator", Role.RESEARCHER)

# Identities the system uses itself. Keys may not be issued in these names: runs requested
# by some of them are public demo runs.
RESERVED_OWNERS = frozenset(
    {"guest", "demo-researcher", "demo-approver", "local-operator", "replay", "unauthenticated"}
)


def hash_key(key: str) -> str:
    return sha256_hex(key.encode("utf-8"))


class ApiKeyService:
    def __init__(self, repo: ApiKeyRepository, clock: Clock):
        self.repo = repo
        self.clock = clock

    def create(self, owner: str, role: Role | str) -> tuple[str, str]:
        """Create a key. Returns (key_id, plaintext key); the plaintext is not stored."""
        role = Role(role)
        if role is Role.GUEST:
            raise InvalidInputError("guest access needs no key")
        if not owner or len(owner) > 120:
            raise InvalidInputError("owner must be 1-120 characters")
        if owner.strip().lower() in RESERVED_OWNERS:
            raise InvalidInputError(f"{owner!r} is a reserved identity")
        key_id = secrets.token_hex(6)
        key = f"rsf_{key_id}_{secrets.token_urlsafe(32)}"
        self.repo.add(key_id, hash_key(key), owner, str(role), self.clock.now())
        return key_id, key

    def verify(self, key: str | None) -> Principal | None:
        if not key or not key.startswith("rsf_"):
            return None
        record = self.repo.find_by_hash(hash_key(key))
        if record is None or record["revoked_at"] is not None:
            return None
        if not hmac.compare_digest(record["key_hash"], hash_key(key)):
            return None
        return Principal(record["owner"], Role(record["role"]), record["key_id"])

    def revoke(self, key_id: str) -> None:
        self.repo.revoke(key_id, self.clock.now())


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None
