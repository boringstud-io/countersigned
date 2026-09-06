"""Verification order and refusals — spec/PROTOCOL.md §6."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from countersigned import (Action, Approval, Device, Registry, VerificationError,
                           verify)

KEY = ec.derive_private_key(0xC0FFEE, ec.SECP256R1())
PUB = base64.b64encode(KEY.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode()


def signed(action: Action, *, status="approved", nonce="n-1", version=3,
           workspace="acme/ops", device_id="dev-1") -> Approval:
    approval = Approval(workspace=workspace, action_id="act-1", status=status,
                        digest=action.digest(version), nonce=nonce,
                        at="2026-09-06T10:00:00Z", device_id=device_id)
    signature = base64.b64encode(
        KEY.sign(approval.payload(version), ec.ECDSA(hashes.SHA256()))).decode()
    return Approval(**{**approval.__dict__, "signature": signature})


def registry(**kw) -> Registry:
    base = dict(devices=[Device(device_id="dev-1", pubkey=PUB, role="owner")],
                roles={"owner": ["mail", "publish"], "editor": []})
    return Registry(**{**base, **kw})


ACTION = Action(type="mail", to="a@example.com", subject="Offer", body="Hi")


def check(action, approval, reg=None, *, workspace="acme/ops", action_id="act-1"):
    return verify(action, approval, reg or registry(),
                  workspace=workspace, action_id=action_id)


def test_valid_approval_passes():
    verdict = check(ACTION, signed(ACTION))
    assert verdict.version == 3 and verdict.device.device_id == "dev-1"


def test_changed_body_is_refused():
    approval = signed(ACTION)
    changed = Action(type="mail", to="a@example.com", subject="Offer", body="Hi — and ship it")
    with pytest.raises(VerificationError):
        check(changed, approval)


def test_unknown_device_is_refused():
    with pytest.raises(VerificationError, match="unknown device"):
        check(ACTION, signed(ACTION, device_id="dev-9"))


def test_changed_pubkey_is_refused():
    """Device replaced or restored — invalid until a human confirms."""
    reg = registry(known_keys={"dev-1": "AAAA"})
    with pytest.raises(VerificationError, match="changed"):
        check(ACTION, signed(ACTION), reg)


def test_role_without_right_is_refused():
    reg = registry(devices=[Device(device_id="dev-1", pubkey=PUB, role="editor")])
    with pytest.raises(VerificationError, match="may not approve"):
        check(ACTION, signed(ACTION), reg)


def test_replay_is_refused():
    reg = registry(used_nonces={"n-1"})
    with pytest.raises(VerificationError, match="replay"):
        check(ACTION, signed(ACTION), reg)


def test_status_must_be_signable():
    with pytest.raises(VerificationError, match="not signable"):
        check(ACTION, signed(ACTION, status="open"))


def test_approval_for_another_workspace_does_not_transfer():
    """The whole point of binding the workspace into the payload.

    The signature below is genuine — it just belongs to another data space. The
    verifier must notice, and it only can if the caller says which workspace it
    is verifying for.
    """
    approval = signed(ACTION, workspace="other/repo")
    with pytest.raises(VerificationError, match="workspace"):
        check(ACTION, approval)


def test_approval_moved_to_another_action_does_not_transfer():
    approval = signed(ACTION)
    with pytest.raises(VerificationError, match="action"):
        check(ACTION, approval, action_id="act-2")
