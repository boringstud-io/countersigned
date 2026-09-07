# Test vectors

`vectors.json` is the contract between implementations of this protocol. Every implementation
must pass every vector. If Swift and Python disagree, one of them is wrong — and without these
vectors nobody notices until a real approval is rejected or a forged one accepted.

## Kinds of vector

| `expect` | meaning |
|---|---|
| `valid` | canonical form, digest and signature all match |
| `invalid` + `reason` | must be refused — see the two classes below |

There are **two ways to be invalid**, and conflating them hides bugs:

- **Content changed.** The signature still verifies against its payload — it was made over
  bytes that did not change. What breaks is the link between the payload's digest and the
  action's content (`tampered-body`, `tampered-cc`).
- **Binding wrong.** The digest matches, the signature verifies, and the approval still must
  be refused because it belongs to another workspace or another action (`foreign-workspace`).
  Such vectors carry `verify_for`, naming the context the verifier is checking for.

An implementation that only checks signatures passes the first class and fails the second.

## `production`

`production-signature` is a real approval from the system running in production, made in the
owner's Secure Enclave on 2026-09-07. An implementation that reproduces its canonical form,
digest and payload — and verifies its signature — verifies what the *deployed* system actually
produces, not only what this repository makes. Without such a vector the suite proves only that
the two implementations here agree with each other.

**How it came to exist, because the detour is the interesting part.** The first attempt was
withdrawn before release: its action id was `go-villa-svs-2`, and the `svs` identified a real
business contact. The id sits inside the signed payload, so it cannot be renamed without
destroying the signature — and every one of the 80 signed actions in that workspace names a
person, a studio or a company. There was no neutral candidate.

The fix was to create an action *for this purpose*: recipient `vector@example.com` (RFC 2606,
goes nowhere), a body that explains itself, an id that names nobody, and a rule on the sending
side that refuses any card whose id starts with `go-public-`. It was signed like any other
action and is never sent — so unlike the first attempt, its content can be published in full.

A vector may still carry `content_withheld` instead, publishing only payload, signature and
key. That form exists for cases where the content must stay private; this one does not need it.

## Regenerating

Vectors are generated with a fixed test key (`0x1c0ffee5…`). That key is public by design and
must never be used for anything real.
