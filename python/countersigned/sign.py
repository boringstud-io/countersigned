"""Signing — the other half of spec/PROTOCOL.md §5.

The package deliberately does not choose a key store. It takes something that
can sign, and asks it for exactly one thing: a DER signature over the payload
bytes. The reference app hands it a Secure Enclave key that never leaves the
device; a demo or a test hands it :class:`SoftwareKey`.

That distinction is the whole point, so the package refuses to blur it: a
software key knows it is one, and any output derived from it says so.
"""

from __future__ import annotations

import base64
import secrets
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .canonical import Action
from .payload import Approval

SIGNABLE = ("approved", "rejected")


@runtime_checkable
class SigningKey(Protocol):
    """Anything that can countersign. Two members, on purpose.

    An implementation backed by a secure element cannot export its private key,
    so nothing here may ask for one.
    """

    @property
    def public_key_b64(self) -> str:
        """Base64 of the uncompressed SEC1 point — what the registry stores."""

    @property
    def is_hardware_backed(self) -> bool:
        """False for keys that a process can copy. Demos must say so out loud."""

    def sign(self, payload: bytes) -> bytes:
        """ECDSA P-256 / SHA-256, DER-encoded."""


class SoftwareKey:
    """A P-256 key in ordinary memory.

    Not a secure element: whoever can read the process or the file can sign as
    this device. Use it for demos, tests and CI — never to represent a person.
    """

    def __init__(self, private_key: ec.EllipticCurvePrivateKey) -> None:
        self._key = private_key

    @classmethod
    def generate(cls) -> SoftwareKey:
        return cls(ec.generate_private_key(ec.SECP256R1()))

    @classmethod
    def from_pem(cls, pem: bytes) -> SoftwareKey:
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise ValueError("not an elliptic-curve private key")
        if not isinstance(key.curve, ec.SECP256R1):
            raise ValueError(f"wrong curve: {key.curve.name}, expected secp256r1")
        return cls(key)

    def pem(self) -> bytes:
        return self._key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption())

    @property
    def public_key_b64(self) -> str:
        point = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint)
        return base64.b64encode(point).decode("ascii")

    @property
    def is_hardware_backed(self) -> bool:
        return False

    def sign(self, payload: bytes) -> bytes:
        return self._key.sign(payload, ec.ECDSA(hashes.SHA256()))


def approve(action: Action, *, key: SigningKey, workspace: str, action_id: str,
            device_id: str, status: str = "approved", version: int = 3,
            protocol: str = "nino-go", nonce: str | None = None,
            at: str | None = None) -> Approval:
    """Countersign one action and return the finished approval.

    ``workspace`` and ``action_id`` are bound into the signed bytes, which is
    what lets the verifier refuse an approval that was made for something else.
    The nonce is generated here unless given: it is what makes an approval
    single-use, so it must never be derived from the action's own content.
    """
    if status not in SIGNABLE:
        raise ValueError(f"status is not signable: {status!r} (expected one of {SIGNABLE})")

    unsigned = Approval(
        workspace=workspace, action_id=action_id, status=status,
        digest=action.digest(version),
        nonce=nonce or secrets.token_hex(16),
        at=at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        device_id=device_id)
    signature = key.sign(unsigned.payload(version, protocol))
    return Approval(**{**unsigned.__dict__,
                       "signature": base64.b64encode(signature).decode("ascii")})
