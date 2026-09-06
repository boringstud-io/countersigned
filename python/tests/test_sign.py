"""The signing half. Every test here is one sentence about the protocol."""

import base64

import pytest
from countersigned import (Action, Device, Registry, SoftwareKey, VerificationError,
                           approve, verify)

WORKSPACE = "owner/repo"
ACTION_ID = "go-2026-09-06-01"


def registry_for(key: SoftwareKey, role: str = "owner") -> Registry:
    return Registry(devices=[Device("iphone", key.public_key_b64, role, "Demo")],
                    roles={role: ["email"]})


def an_action() -> Action:
    return Action(type="email", to="studio@example.com", subject="Offer",
                  body="Attached.", attachments=["offer.pdf"])


@pytest.mark.parametrize("version", [3, 4])
def test_what_this_package_signs_it_also_verifies(version):
    key = SoftwareKey.generate()
    action = an_action()
    approval = approve(action, key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                       device_id="iphone", version=version)
    verdict = verify(action, approval, registry_for(key),
                     workspace=WORKSPACE, action_id=ACTION_ID)
    assert verdict.version == version
    assert verdict.device.device_id == "iphone"


def test_a_rejection_is_signed_the_same_way_as_an_approval():
    key = SoftwareKey.generate()
    action = an_action()
    approval = approve(action, key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                       device_id="iphone", status="rejected")
    assert verify(action, approval, registry_for(key),
                  workspace=WORKSPACE, action_id=ACTION_ID).version == 3


def test_only_a_decision_can_be_signed():
    # "open" is a state, not a decision. Signing one would mean a device
    # asserting something it cannot assert.
    with pytest.raises(ValueError, match="not signable"):
        approve(an_action(), key=SoftwareKey.generate(), workspace=WORKSPACE,
                action_id=ACTION_ID, device_id="iphone", status="open")


def test_an_approval_does_not_travel_to_another_action():
    key = SoftwareKey.generate()
    action = an_action()
    approval = approve(action, key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                       device_id="iphone")
    with pytest.raises(VerificationError, match="not 'go-other'"):
        verify(action, approval, registry_for(key),
               workspace=WORKSPACE, action_id="go-other")


def test_an_approval_does_not_travel_to_another_workspace():
    key = SoftwareKey.generate()
    action = an_action()
    approval = approve(action, key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                       device_id="iphone")
    with pytest.raises(VerificationError, match="not 'someone/else'"):
        verify(action, approval, registry_for(key),
               workspace="someone/else", action_id=ACTION_ID)


def test_changing_one_character_of_the_action_breaks_the_approval():
    key = SoftwareKey.generate()
    approval = approve(an_action(), key=key, workspace=WORKSPACE,
                       action_id=ACTION_ID, device_id="iphone")
    tampered = Action(type="email", to="attacker@example.com", subject="Offer",
                      body="Attached.", attachments=["offer.pdf"])
    with pytest.raises(VerificationError, match="does not verify"):
        verify(tampered, approval, registry_for(key),
               workspace=WORKSPACE, action_id=ACTION_ID)


def test_each_approval_gets_its_own_nonce():
    key = SoftwareKey.generate()
    nonces = {approve(an_action(), key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                      device_id="iphone").nonce for _ in range(50)}
    assert len(nonces) == 50


def test_a_role_that_may_not_approve_this_type_is_refused():
    key = SoftwareKey.generate()
    action = an_action()
    approval = approve(action, key=key, workspace=WORKSPACE, action_id=ACTION_ID,
                       device_id="iphone")
    registry = registry_for(key, role="reader")
    registry.roles["reader"] = ["note"]
    with pytest.raises(VerificationError, match="may not approve"):
        verify(action, approval, registry, workspace=WORKSPACE, action_id=ACTION_ID)


def test_a_software_key_survives_a_pem_round_trip():
    key = SoftwareKey.generate()
    restored = SoftwareKey.from_pem(key.pem())
    assert restored.public_key_b64 == key.public_key_b64
    action = an_action()
    approval = approve(action, key=restored, workspace=WORKSPACE,
                       action_id=ACTION_ID, device_id="iphone")
    assert verify(action, approval, registry_for(key),
                  workspace=WORKSPACE, action_id=ACTION_ID).version == 3


def test_a_software_key_admits_that_it_is_one():
    # The demo leans on this: a laptop must not look like a Secure Enclave.
    assert SoftwareKey.generate().is_hardware_backed is False


def test_a_key_on_the_wrong_curve_is_refused_at_load_time():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    other = ec.generate_private_key(ec.SECP384R1()).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption())
    with pytest.raises(ValueError, match="wrong curve"):
        SoftwareKey.from_pem(other)


def test_the_signature_is_der_not_raw():
    # Raw r||s is 64 bytes; DER carries a SEQUENCE header. The app's verifier
    # expects DER, so a signer that emits raw would fail only in production.
    key = SoftwareKey.generate()
    approval = approve(an_action(), key=key, workspace=WORKSPACE,
                       action_id=ACTION_ID, device_id="iphone")
    raw = base64.b64decode(approval.signature)
    assert raw[0] == 0x30 and len(raw) != 64
