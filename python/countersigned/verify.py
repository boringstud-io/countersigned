"""Verification — spec/PROTOCOL.md §6.

The order of the checks is part of the protocol: cheap and unambiguous checks
first, so a failure names exactly one cause. Verification is side-effect free;
consuming the nonce is a separate, explicit step.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from .canonical import Action
from .payload import Approval

#: Newest first — the first version that verifies wins.
VERSIONS = (4, 3, 2, 1)


class VerificationError(Exception):
    """Refusal with a reason. The reason is the product: it must name one cause."""


@dataclass(frozen=True)
class Device:
    device_id: str
    pubkey: str          # base64 of the uncompressed SEC1 point
    role: str = ""
    name: str = ""


@dataclass(frozen=True)
class Verdict:
    device: Device
    version: int


@dataclass
class Registry:
    """Devices, roles and consumed nonces of one workspace."""

    devices: list[Device] = field(default_factory=list)
    #: role -> action types this role may approve
    roles: dict[str, list[str]] = field(default_factory=dict)
    used_nonces: set[str] = field(default_factory=set)
    #: device_id -> pubkey as last seen. A changed key means replacement or
    #: restore and invalidates until a human confirms.
    known_keys: dict[str, str] = field(default_factory=dict)

    def device(self, device_id: str) -> Device | None:
        return next((d for d in self.devices if d.device_id == device_id), None)


def verify(action: Action, approval: Approval, registry: Registry, *,
           workspace: str, action_id: str,
           protocol: str = "nino-go", accepted_versions=VERSIONS) -> Verdict:
    """Check an approval. Raises VerificationError; returns the verdict on success.

    ``workspace`` and ``action_id`` are what the *caller* is verifying for — not
    what the approval claims. They must be passed, and they are checked first.

    This is not ceremony. The payload binds both values, but a signature only
    proves that *someone* signed *that* payload; it says nothing about whether
    the payload belongs here. Without this check, an approval taken from another
    workspace — or from another action in the same one — verifies happily.
    Found by a test on 2026-09-06, before this package had any user.
    """
    if approval.workspace != workspace:
        raise VerificationError(
            f"approval is for workspace {approval.workspace!r}, not {workspace!r}")
    if approval.action_id != action_id:
        raise VerificationError(
            f"approval is for action {approval.action_id!r}, not {action_id!r}")
    if approval.status not in ("approved", "rejected"):
        raise VerificationError(f"status is not signable: {approval.status}")

    device = registry.device(approval.device_id)
    if device is None:
        raise VerificationError(f"unknown device: {approval.device_id}")

    seen = registry.known_keys.get(device.device_id)
    if seen is not None and seen != device.pubkey:
        raise VerificationError(
            f"public key of {device.device_id} changed — device replaced or restored; "
            "invalid until confirmed by a human")

    try:
        point = base64.b64decode(device.pubkey)
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
        signature = base64.b64decode(approval.signature)
    except Exception as exc:  # noqa: BLE001 — any malformed input is one cause
        raise VerificationError("malformed key or signature") from exc

    version = None
    for candidate in accepted_versions:
        if candidate < 3:
            # v1/v2 predate the canonical form; this package verifies v3 and up.
            continue
        expected = approval.digest
        if action.digest(candidate) != expected:
            continue
        try:
            public_key.verify(signature, approval.payload(candidate, protocol),
                              ec.ECDSA(hashes.SHA256()))
            version = candidate
            break
        except InvalidSignature:
            continue
    if version is None:
        raise VerificationError("signature does not verify for any accepted version")

    allowed = registry.roles.get(device.role)
    if allowed is None:
        raise VerificationError(f"unknown role: {device.role}")
    if action.type not in allowed:
        raise VerificationError(f"role {device.role} may not approve type {action.type}")

    if approval.nonce in registry.used_nonces:
        raise VerificationError("nonce already used (replay)")

    return Verdict(device=device, version=version)


def verify_payload(payload: bytes, signature_b64: str, pubkey_b64: str) -> bool:
    """Check a raw payload against a key — without the action's content.

    Used for production vectors, where the body stays private but the signature
    is real.
    """
    try:
        point = base64.b64decode(pubkey_b64)
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
        public_key.verify(base64.b64decode(signature_b64), payload,
                          ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:  # noqa: BLE001
        return False
