"""The signed payload — spec/PROTOCOL.md §5."""

from __future__ import annotations

from dataclasses import dataclass

SEPARATOR = "|"


@dataclass(frozen=True)
class Approval:
    """What a device asserts when it countersigns an action."""

    workspace: str      # "owner/repo" — the data space this approval is bound to
    action_id: str
    status: str         # "approved" or "rejected"; nothing else is signable
    digest: str
    nonce: str
    at: str             # ISO-8601
    device_id: str
    #: base64 DER. Empty while building a payload to sign; set once signed.
    signature: str = ""

    def payload(self, version: int = 3, protocol: str = "nino-go") -> bytes:
        """The exact bytes the signature is made over.

        No field may contain the separator; that is checked, because a payload
        that can be re-split differently is a payload that can be forged.
        """
        parts = [f"{protocol}-v{version}", self.workspace, self.action_id,
                 self.status, self.digest, self.nonce, self.at, self.device_id]
        for part in parts:
            if SEPARATOR in part:
                raise ValueError(f"payload field contains {SEPARATOR!r}: {part!r}")
        return SEPARATOR.join(parts).encode("utf-8")
