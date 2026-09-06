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

A vector marked `content_withheld` comes from the system running in production. Its payload,
signature and public key are published; the action's content is not. Such a vector proves that
an implementation verifies signatures made by the *deployed* system rather than only signatures
this repository made itself.

**There is currently no such vector, and that is a known gap.** The first one was withdrawn
before release: the action id sits inside the signed payload, so it cannot be renamed without
destroying the signature — and every action id in that production workspace names a person, a
studio or a company. Publishing one would have published a business contact.

It is restored by signing a single action created for the purpose, whose id names nobody. Until
then `test_production_signature_verifies` skips, and the skip is printed on every run rather
than quietly passing.

## Regenerating

Vectors are generated with a fixed test key (`0x1c0ffee5…`). That key is public by design and
must never be used for anything real.
