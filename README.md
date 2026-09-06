# countersigned

[![tests](https://github.com/boringstud-io/countersigned/actions/workflows/tests.yml/badge.svg)](https://github.com/boringstud-io/countersigned/actions/workflows/tests.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

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

It has been running a real business since August 2026. What that produced, counted from the
files — including the incident it did **not** prevent — is in
[CASE-STUDY.md](CASE-STUDY.md).

## Try it in five minutes

```bash
git clone https://github.com/boringstud-io/countersigned
cd countersigned/examples && ./demo.sh
```

An agent proposes and cannot send. A human countersigns and it runs — once. Then the file is
edited after signing, and the check catches it and names the line. Needs Python 3.10+ and, the
first time, the network. No account, no server, no model.
[What it prints](examples/README.md) · [the ninety-second version](examples/TALK.md)

## What is here

| | |
|---|---|
| [`spec/PROTOCOL.md`](spec/PROTOCOL.md) | The canonical form, the payload, the verification order, and the gaps it does not close |
| [`spec/DATA-CONTRACT.md`](spec/DATA-CONTRACT.md) | The files the actions live in, and the rule that costs data if ignored |
| [`python/`](python/) | Verifying and signing, 54 tests |
| [`swift/`](swift/) | The same, for iOS and macOS, 33 tests |
| [`vectors/vectors.json`](vectors/vectors.json) | Ten vectors both implementations read from the same file — not a copy each |
| [`examples/`](examples/) | The five-minute demo |
| [`runner/`](runner/) | A job runner with no platform under it: the protocol does not need one |
| [`SECURITY.md`](SECURITY.md) | The threat model, and the section saying what this does **not** guarantee |
| [`CASE-STUDY.md`](CASE-STUDY.md) | Nineteen days of real operation, every number with the command behind it |

## Status

Research preview, extracted from a system that is in daily use. The protocol is the deployed
one: every v3 signature the production workspace has ever made — 80 of them — verifies with
the package in this repository, unchanged.

Not yet here: the case study, and the v4 cutover (`cc` in the canonical form) on the signing
side. v4 verifies today; nothing signs it in production yet, deliberately — the reading side
ships before the writing side.

## Contributing

Issues and pull requests are welcome; [CONTRIBUTING.md](CONTRIBUTING.md) says what is likely to
be accepted and what is not. The short version: the specification is the product, so a change to
`spec/` needs a reason both implementations can be held to, and every protocol change needs a
vector.

For anything that looks like a vulnerability, use GitHub's private vulnerability reporting
rather than an issue — see [SECURITY.md](SECURITY.md).

## License

Apache 2.0.
