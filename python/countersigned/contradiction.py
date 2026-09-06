"""Contradiction detection — spec/PROTOCOL.md §7.

Signatures prove that an action was approved. They cannot prove that nothing
else happened. This pass compares three sources — the actions, the send log and
the approvals — and reports where they disagree.

It found the real incident of 2026-08-25, when a message went out that had been
rejected. The system did not prevent it; it noticed. Both matter, and only this
half is cheap.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Contradiction(Enum):
    REJECTED_BUT_SENT = "rejected_but_sent"
    UNDECIDED_BUT_SENT = "undecided_but_sent"
    IN_SEND_LOG_WITHOUT_APPROVAL = "in_send_log_without_approval"
    SENT_WITHOUT_PROOF = "sent_without_proof"
    APPROVED_BUT_NOT_EXECUTED = "approved_but_not_executed"

    @property
    def is_incident(self) -> bool:
        """Incidents are things that happened and should not have.

        The rest are warnings: something is missing or late, but nothing left
        the system without cover.
        """
        return self in (Contradiction.REJECTED_BUT_SENT,
                        Contradiction.UNDECIDED_BUT_SENT,
                        Contradiction.IN_SEND_LOG_WITHOUT_APPROVAL)

    def message(self, when: str) -> str:
        return {
            Contradiction.REJECTED_BUT_SENT: f"Rejected — but it was sent on {when}",
            Contradiction.UNDECIDED_BUT_SENT: f"Not decided yet — but it was sent on {when}",
            Contradiction.IN_SEND_LOG_WITHOUT_APPROVAL:
                f"The send log shows a send on {when} — but this action is not approved",
            Contradiction.SENT_WITHOUT_PROOF:
                f"Sent on {when} without a verifiable approval",
            Contradiction.APPROVED_BUT_NOT_EXECUTED:
                f"Approved on {when} — the executor has not picked it up",
        }[self]


@dataclass(frozen=True)
class Finding:
    action_id: str
    case: Contradiction
    when: str

    @property
    def is_incident(self) -> bool:
        return self.case.is_incident

    def __str__(self) -> str:
        return f"[{'incident' if self.is_incident else 'warning'}] {self.action_id}: " \
               f"{self.case.message(self.when)}"


@dataclass(frozen=True)
class ActionRecord:
    """What the detector needs to know about an action. Deliberately minimal:
    an implementation maps its own records onto this."""

    action_id: str
    status: str                     # approved | rejected | open | …
    sent_at: str | None = None      # the action's own record of having been sent
    has_valid_signature: bool = False
    approved_at: str | None = None


def find_contradictions(actions: list[ActionRecord],
                        send_log: dict[str, str] | None = None,
                        executed: set[str] | None = None) -> list[Finding]:
    """Compare records, send log and execution state.

    ``send_log`` maps action id -> timestamp, as recorded by whatever actually
    sends. ``executed`` are the ids the executor has consumed. Both are optional:
    with fewer sources the pass reports less, never more.
    """
    send_log = send_log or {}
    executed = executed if executed is not None else set()
    findings: list[Finding] = []

    for action in actions:
        sent_at = action.sent_at or send_log.get(action.action_id)

        if sent_at:
            if action.status == "rejected":
                findings.append(Finding(action.action_id,
                                        Contradiction.REJECTED_BUT_SENT, sent_at))
            elif action.status != "approved":
                findings.append(Finding(action.action_id,
                                        Contradiction.UNDECIDED_BUT_SENT, sent_at))
            elif not action.has_valid_signature:
                findings.append(Finding(action.action_id,
                                        Contradiction.SENT_WITHOUT_PROOF, sent_at))
        elif action.status == "approved" and action.action_id not in executed \
                and action.approved_at:
            findings.append(Finding(action.action_id,
                                    Contradiction.APPROVED_BUT_NOT_EXECUTED,
                                    action.approved_at))

    known = {a.action_id for a in actions}
    approved = {a.action_id for a in actions if a.status == "approved"}
    for action_id, when in send_log.items():
        if action_id not in known or action_id not in approved:
            if not any(f.action_id == action_id for f in findings):
                findings.append(Finding(action_id,
                                        Contradiction.IN_SEND_LOG_WITHOUT_APPROVAL, when))
    return findings
