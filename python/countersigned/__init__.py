"""countersigned — an agent may prepare anything; nothing leaves without a signature.

    from countersigned import Action, Approval, Registry, Device, verify

See spec/PROTOCOL.md for the wire format this implements.
"""

from .canonical import Action, digest_of, one_line
from .contradiction import Contradiction, Finding, find_contradictions
from .payload import Approval
from .verify import Device, Registry, Verdict, VerificationError, verify, verify_payload

__all__ = [
    "Action", "Approval", "Device", "Registry", "Verdict", "VerificationError",
    "Contradiction", "Finding", "find_contradictions",
    "verify", "verify_payload", "digest_of", "one_line",
]
__version__ = "0.1.0"
