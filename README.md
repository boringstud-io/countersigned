# countersigned

**An agent may prepare anything. Nothing reaches the outside world without a human signature.**

## The problem

Agents can read your mail, draft the reply, and send it. The last step is the one that matters — and today it is a button, a checkbox, or a prompt that says "are you sure?". None of that tells you, a week later, *what exactly* was approved, *by whom*, *on which device*, and whether the file changed between the approval and the send.

## What this is

A small protocol and two reference implementations for **countersigned actions**:

1. The agent writes the action — recipient, subject, attachments, text — as a file.
2. The action is reduced to a **canonical form** and hashed.
3. A human signs the hash with a **device-bound key** (Secure Enclave on iOS). The signature covers the exact content, a nonce, the device, and the workspace.
4. Before execution, the executing side **verifies** the signature against the device registry and consumes the nonce. No valid signature, no send. A changed file, no send. A replayed nonce, no send.
5. Afterwards, a **contradiction detector** compares what was signed with what actually went out — and reports the cases where they disagree.

It has been running a real business since August 2026 (see `spec/` for the case study when it lands).

## Status

Research preview. The specification, the Swift package, the Python package, the test vectors, a minimal runner and a five-minute demo are being extracted from a working system into this repository. Watch the commits.

## License

Apache 2.0.
