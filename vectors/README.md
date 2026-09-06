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

## `content_withheld`

`production-signature` comes from a system running in production since August 2026. Its
payload, signature and public key are published; the action's content is not. It proves that
an implementation verifies signatures made by the deployed system — without disclosing what
was signed.

## Regenerating

Vectors are generated with a fixed test key (`0x1c0ffee5…`). That key is public by design and
must never be used for anything real.
