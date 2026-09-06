"""Contradiction detection — spec/PROTOCOL.md §7."""

from countersigned import Contradiction, find_contradictions
from countersigned.contradiction import ActionRecord


def test_rejected_but_sent_is_an_incident():
    """The real case of 2026-08-25."""
    findings = find_contradictions([
        ActionRecord("act-1", status="rejected", sent_at="2026-08-25T09:00:00Z")])
    assert [f.case for f in findings] == [Contradiction.REJECTED_BUT_SENT]
    assert findings[0].is_incident


def test_sent_while_undecided_is_an_incident():
    findings = find_contradictions([
        ActionRecord("act-2", status="open", sent_at="2026-08-29T09:00:00Z")])
    assert findings[0].case is Contradiction.UNDECIDED_BUT_SENT


def test_sent_without_proof_is_a_warning_not_an_incident():
    """Approved and sent, but no signature verifies today — worth showing,
    not the same as sending against a decision."""
    findings = find_contradictions([
        ActionRecord("act-3", status="approved", sent_at="2026-08-18T09:00:00Z",
                     has_valid_signature=False)])
    assert findings[0].case is Contradiction.SENT_WITHOUT_PROOF
    assert not findings[0].is_incident


def test_send_log_entry_without_any_action():
    findings = find_contradictions([], send_log={"act-ghost": "2026-09-01T10:00:00Z"})
    assert findings[0].case is Contradiction.IN_SEND_LOG_WITHOUT_APPROVAL
    assert findings[0].is_incident


def test_approved_and_sent_with_proof_is_silent():
    findings = find_contradictions([
        ActionRecord("act-4", status="approved", sent_at="2026-09-01T10:00:00Z",
                     has_valid_signature=True)])
    assert findings == []


def test_approved_but_never_executed_is_a_warning():
    findings = find_contradictions(
        [ActionRecord("act-5", status="approved", approved_at="2026-09-01T10:00:00Z")],
        executed=set())
    assert findings[0].case is Contradiction.APPROVED_BUT_NOT_EXECUTED
    assert not findings[0].is_incident
