"""The vectors are the contract between the implementations.

Every implementation of this protocol must pass every vector in
``vectors/vectors.json``. If Swift and Python disagree, one of them is wrong —
and without these vectors nobody would notice until a real approval is rejected.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from countersigned import Action, Approval, digest_of, verify_payload

VECTORS = json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "vectors" / "vectors.json").read_text()
)
PROTOCOL = VECTORS["protocol"]
CASES = VECTORS["vectors"]


def ids(cases):
    return [c["name"] for c in cases]


@pytest.mark.parametrize("case", CASES, ids=ids(CASES))
def test_signature_always_verifies_against_its_own_payload(case):
    """Every vector's signature is genuine — including the tampered ones.

    This is the subtle part of the protocol: tampering with the *action* does
    not break the signature, because the signature was made over the payload and
    the payload has not changed. What breaks is the link between the payload's
    digest and the action's content. Testing it this way keeps the two apart —
    ``test_tampering_breaks_the_link`` covers the other half.
    """
    assert verify_payload(case["payload"].encode(), case["signature"], case["pubkey"]), \
        case.get("note", case["name"])


CONTENT_CASES = [c for c in CASES if not c.get("content_withheld")]


@pytest.mark.parametrize("case", CONTENT_CASES, ids=ids(CONTENT_CASES))
def test_canonical_form_and_digest(case):
    """Rebuild the canonical form from the action and compare byte for byte."""
    action = Action(**case["action"])
    assert action.canonical(case["version"]) == case["canonical"]
    assert action.digest(case["version"]) == case["digest"]
    assert digest_of(case["canonical"]) == case["digest"]


#: Two kinds of "invalid" exist and must not be conflated: the content was
#: changed (the digest no longer matches), or the binding is wrong (the digest
#: matches fine, but the approval belongs to another workspace or action).
TAMPERED = [c for c in CONTENT_CASES
            if c["expect"] == "invalid" and not c.get("verify_for")]


@pytest.mark.parametrize("case", TAMPERED, ids=ids(TAMPERED))
def test_tampering_breaks_the_link(case):
    """A changed action no longer matches the signed payload.

    The signature itself still verifies — it was made over the original bytes.
    What breaks is the link between payload and content, and that is exactly
    what verification checks.
    """
    action = Action(**case["action"])
    signed_digest = case["payload"].split("|")[4]
    assert action.digest(case["version"]) != signed_digest, case["reason"]


def test_v4_without_cc_is_not_v3():
    """The empty cc line is still a line. Confusing the two would let a v3
    signature pass as v4 — and v3 does not cover cc."""
    action = Action(type="mail", to="a@example.com", subject="Offer", body="Hi")
    assert action.digest(3) != action.digest(4)
    assert "\ncc=\n" in action.canonical(4)
    assert "cc=" not in action.canonical(3)


BOUND = [c for c in CASES if c.get("verify_for")]


@pytest.mark.parametrize("case", BOUND, ids=ids(BOUND))
def test_binding_is_checked_not_just_the_signature(case):
    """A signature for another workspace or action must be refused.

    The signature itself is genuine — that is the trap. Only a verifier that
    compares the payload's binding against its own context catches it.
    """
    from countersigned import Approval, Device, Registry, VerificationError, verify

    fields = case["payload"].split("|")
    approval = Approval(workspace=fields[1], action_id=fields[2], status=fields[3],
                        digest=fields[4], nonce=fields[5], at=fields[6],
                        device_id=fields[7], signature=case["signature"])
    registry = Registry(devices=[Device(device_id=fields[7], pubkey=case["pubkey"],
                                        role="owner")],
                        roles={"owner": ["mail", "publish"]})
    with pytest.raises(VerificationError):
        verify(Action(**case["action"]), approval, registry,
               workspace=case["verify_for"]["workspace"],
               action_id=case["verify_for"]["action_id"])


def test_production_signature_present():
    """One vector must come from the deployed system — otherwise the suite only
    proves that we agree with ourselves."""
    assert any(c.get("content_withheld") for c in CASES), \
        "no production vector: the suite would only test itself"
