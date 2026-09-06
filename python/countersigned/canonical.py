"""The canonical form — the exact bytes that get signed.

Specified in spec/PROTOCOL.md §3. Every rule here is load-bearing; see the
incident note on whitespace folding, which cost a valid approval once.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

#: Field keys are part of the signed bytes and are therefore fixed forever.
#: They are German because that is what the deployed system signs; renaming
#: them would change every digest and invalidate existing approvals.
_KEY_TYPE, _KEY_TO, _KEY_CC = "typ", "an", "cc"
_KEY_SUBJECT, _KEY_ATTACHMENTS, _KEY_BODY = "betreff", "anhang", "text"


def one_line(value: str | None) -> str:
    """Collapse every run of whitespace to a single space, then strip.

    Exactly ``" ".join(value.split())``. Not cosmetic: the signing and verifying
    sides once disagreed here — one replaced newlines only, the other folded all
    whitespace — and a subject with two spaces produced two different digests.
    """
    return " ".join((value or "").split())


@dataclass(frozen=True)
class Action:
    """One action with an outside effect."""

    type: str
    body: str
    to: str | None = None
    cc: list[str] = field(default_factory=list)
    subject: str | None = None
    attachments: list[str] = field(default_factory=list)

    def canonical(self, version: int = 3) -> str:
        """The canonical form for the given protocol version.

        v3 has five lines, v4 adds ``cc`` after ``an``. Note that v4 without any
        cc is *not* v3: the empty ``cc=`` line is still there, so the digest
        differs. The two are never interchangeable.
        """
        if version not in (3, 4):
            raise ValueError(f"unsupported canonical version: {version}")
        lines = [f"{_KEY_TYPE}={one_line(self.type)}", f"{_KEY_TO}={one_line(self.to)}"]
        if version >= 4:
            lines.append(f"{_KEY_CC}={_join(self.cc)}")
        lines += [
            f"{_KEY_SUBJECT}={one_line(self.subject)}",
            f"{_KEY_ATTACHMENTS}={_join(self.attachments)}",
            # Last on purpose: the body may contain anything, including newlines.
            f"{_KEY_BODY}={self.body}",
        ]
        return "\n".join(lines)

    def digest(self, version: int = 3) -> str:
        return digest_of(self.canonical(version))


def _join(entries: list[str]) -> str:
    return ",".join(one_line(e) for e in entries)


def digest_of(canonical: str) -> str:
    """SHA-256 over the UTF-8 bytes, lowercase hex."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
