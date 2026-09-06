# The countersigned protocol

Version 3 is in production since 2026-08-26. Version 4 is specified here and not yet active;
see [Version history](#version-history).

Every rule below is implemented twice — once in Swift on the signing side, once in Python on
the verifying side — and every section names the file it was extracted from. Where the two
implementations once disagreed, the incident is recorded, because those are the rules that
actually matter.

---

## 1. What this protocol is for

An agent works on behalf of a person: it reads mail, drafts replies, prepares posts, writes
contracts. Preparing is safe. Sending is not.

This protocol draws the line at the last step. The agent may compose an action and write it to
a file. It may not execute it. Execution requires a signature made by a key that lives on a
person's device, over the exact content of that action. Before anything leaves the system, the
executing side recomputes the content, checks the signature against a device registry, and
burns a nonce so the same approval cannot be replayed.

Three properties follow, and they are the whole point:

- **Specific.** The signature covers *this* recipient, *this* subject, *this* text. Change any
  of them after the fact and verification fails.
- **Attributable.** It names the device, and the device register names the person and role.
- **Auditable.** Approval and execution leave separate records, so a third step can compare
  them and report where they disagree (§7).

What it deliberately does *not* do: judge whether the action is a good idea, prevent a
compromised executor from sending something it never verified, or replace a human reading the
text. It makes "I approved that" a checkable statement instead of a memory.

## 2. Vocabulary

| term | meaning |
|---|---|
| **action** | something with an outside effect: an email, a publication, a contract. Stored as one record in a file. |
| **workspace** | the data space an action belongs to — in the reference implementation, one Git repository. Part of the signature, so an approval cannot be replayed against another workspace. |
| **device** | a phone or laptop holding a private key. The unit of identity; people are named in the registry, not in the signature. |
| **countersignature** | the human signature over an action's canonical digest. |
| **executor** | the side that performs the action after verification. |
| **nonce** | a value unique per approval, consumed at execution. |

## 3. Canonical form

The canonical form is the exact byte string that gets hashed. Both sides must build it
identically, so it is deliberately blunt: plain text, no JSON, no escaping.

### v3 — five lines

```
typ=<type>
an=<recipient>
betreff=<subject>
anhang=<a1,a2,…>
text=<body>
```

*(The keys are German in the deployed version — `typ`, `an`, `betreff`, `anhang`, `text` —
because that is what is signed today. Renaming them changes every digest and would invalidate
existing approvals; v4 keeps them for the same reason. Implementations must use these exact
byte sequences.)*

Rules, all of them load-bearing:

1. **Line separator is LF (`0x0A`). There is no trailing newline.** A trailing newline changes
   the digest. — `SecureEnclaveSigner.swift:195`, `verify_go.py:109-121`
2. **A missing field is the empty string**, never `null`, never omitted. Every action has all
   lines, even one without a recipient. — same
3. **`typ`, `an`, `betreff` and each attachment entry are collapsed to one line**: every run of
   whitespace becomes exactly one space (U+0020), then the value is trimmed. Formally
   `" ".join(value.split())`. — `GoInhalt.einzeilig`, `verify_go.py:_einzeilig`
4. **Attachments are joined with `,`** after each entry is collapsed. An entry containing a
   comma is therefore ambiguous; implementations must reject or escape it (see
   [Known gaps](#10-known-gaps)).
5. **`text` comes last and is passed through unchanged** — no collapsing, no trimming. It may
   contain LF, and everything after `text=` belongs to it. That is why it is last.
6. **Encoding is UTF-8.** The digest is over the UTF-8 bytes of the string as it appears in the
   JSON after parsing — no normalisation, no re-encoding. — `SecureEnclaveSigner.swift:127`

> **Incident, 2026-08-26.** Rule 3 originally said only "newlines become spaces" on the signing
> side, while the verifying side already collapsed *all* whitespace. A subject containing two
> spaces or a tab produced two different digests, and a genuine approval would have been
> rejected as invalid. Found before the v3 cutover, fixed by aligning the signer. The lesson is
> in the rule's wording: normalisation must be specified as an operation, not as an intent.

### v4 — six lines, adds `cc`

```
typ=<type>
an=<recipient>
cc=<c1,c2,…>
betreff=<subject>
anhang=<a1,a2,…>
text=<body>
```

`cc` is formatted like `anhang`: each entry collapsed per rule 3, joined with `,`, empty when
unset. It sits directly after `an` because it is part of the recipient set.

**Why v4 exists.** In v3, `cc` was carried in the record but not in the canonical form. An
approval therefore did not cover who else received the message: anyone able to write the file
between approval and execution could add a recipient without breaking the signature. This was
found on 2026-09-05 while extracting the protocol, and reported before it could be used — no
production action ever carried a `cc`.

**Note that v4 without any `cc` is not v3.** The empty `cc=` line is still there, so the digest
differs. Implementations must not treat the two as interchangeable.

## 4. Digest

```
digest = lowercase_hex( SHA-256( utf8( canonical_form ) ) )
```

— `SecureEnclaveSigner.inhaltsDigest` / `verify_go.v3_digest`

## 5. The signed payload

The signature is made over this byte string, not over the digest alone:

```
<proto>-v<n>|<workspace>|<action-id>|<status>|<digest>|<nonce>|<at>|<device-id>
```

Fields are joined with `|` and none of them may contain `|`.

| field | meaning | protects against |
|---|---|---|
| `<proto>-v<n>` | protocol and version, e.g. `nino-go-v3` | cross-version confusion; a v3 signature never validates as v4 |
| `workspace` | `owner/repo` of the data space | replaying an approval against a different workspace |
| `action-id` | id of the action within the workspace | moving an approval to another action |
| `status` | `approved` or `rejected` — nothing else is signable | turning a rejection into an approval |
| `digest` | §4 | changing recipient, subject, attachments or body |
| `nonce` | unique per approval | replay (§6, step 7) |
| `at` | ISO-8601 timestamp of the approval | — (recorded, not enforced) |
| `device-id` | which device signed | attribution |

Signature algorithm: **ECDSA over P-256 with SHA-256**. Public keys are stored as base64 of the
uncompressed SEC1 point; signatures as base64 DER. — `verify_go.py:216-232`

The private key lives in the device's secure element where available (Secure Enclave on Apple
hardware), otherwise in a software key in the keychain. The protocol does not depend on which —
but an implementation should say which one it used, because it changes what a stolen device means.

## 6. Verification

The executing side runs these checks **in this order** and refuses on the first failure. Order
matters: cheap and unambiguous checks come first, so a failure names one cause.

1. An approval object exists, and its `workspace` and `action-id` are **the ones the
   verifier is checking for** — not merely the ones the approval names. A signature proves
   that someone signed that payload; it does not prove the payload belongs here. Skip this
   and an approval lifted from another workspace, or from another action in the same one,
   verifies happily.
2. `status` is `approved` or `rejected`.
3. `device-id` is present in the device registry.
4. The registry's public key for that device has not changed since it was last seen. A changed
   key means device replacement or restore, and invalidates until a human confirms.
5. Signature verifies against the payload. Versions are tried **newest first** (v4, v3, v2, v1);
   the first that verifies determines the version.
6. The version is still accepted. Retired versions have an end date, not a condition — a
   condition nobody checks is not a rule (`V1_ENDE = 2026-09-01`).
7. The device's role is allowed to approve this action type (`roles.approve_go_types`).
8. The nonce has not been used before.

Only then may the action execute, and execution **consumes** the nonce by appending to the
nonce log. — `verify_go.verify()`, `SignaturPruefung.swift`

> **Found while extracting this specification, 2026-09-06.** The first version of the
> reference implementation checked signature, device, role and nonce — but never compared the
> approval's workspace and action id against the context it was verifying in. The payload
> *binds* both values; nobody *checked* them. A test that moved an approval to another
> workspace passed. This is why step 1 is a step and not an assumption.

Two consequences worth stating: verification is idempotent and side-effect-free until step 8,
so it may be run for display at any time. And the executor is trusted to run it — the protocol
proves that an action *was* approved, not that an executor *checked*. §7 exists for that reason.

## 7. Contradiction detection

Signatures prove approval. They cannot prove that nothing else happened. A second, independent
pass compares three sources — the actions, the send log, and the approvals — and reports:

| case | meaning | severity |
|---|---|---|
| **rejected but sent** | the record says rejected, the send log says it went out | incident |
| **not decided but sent** | sent while still open | incident |
| **in send log without approval** | the log has an entry the actions don't justify | incident |
| **sent without verifiable proof** | sent, but no signature that verifies today | warning |
| **approved but not picked up** | approved N runs ago, executor never acted | warning |

— `GoWiderspruch.Fall`

This is the check that found the real incident of 2026-08-25, when a message went out that had
been rejected. The system did not prevent it; it *noticed* it. An honest protocol needs both,
and only the second one is cheap.

## 8. Device registry

A workspace holds a list of devices:

```json
{ "device_id": "dev-1a2b3c4d",
  "name": "Julian",
  "role": "owner",
  "pubkey": "<base64 SEC1 uncompressed point>",
  "registered_at": "2026-08-17T01:09:28Z" }
```

Roles are defined per workspace and say which action types a role may approve:

```json
{ "roles": { "owner":  { "approve_go_types": ["mail", "publish", "sonstig"] },
             "editor": { "approve_go_types": [] } } }
```

Registration rule: the **first** device in a workspace becomes `owner`, every later one
`editor`. A role is never chosen by the device that registers — a device that could name its own
role could grant itself approval rights. Promotion happens through the workspace, outside the app.

Removing a device from the registry immediately invalidates everything it signs afterwards.
Actions it signed before stay verifiable, which is correct: they were valid when made.

## 9. Nonce log

Append-only, one line per consumed approval:

```
<nonce>|<action-id>|<consumed-at>
```

The log is the replay boundary. It must be written **before** the action executes; a crash
between write and execution costs one action, a crash the other way costs the guarantee.

## Version history

| version | canonical form | active | note |
|---|---|---|---|
| v1 | none — payload without digest | 2026-08-18 … 2026-09-01 | content not covered; retired by date |
| v2 | body only | since 2026-08-18 | still verifiable |
| v3 | five lines (§3) | since 2026-08-26 | current |
| v4 | six lines, adds `cc` | specified, not active | see cutover below |

**Cutover rule, learned from v2→v3:** the verifying side learns the new version *first* and
keeps accepting the old ones. Only when it does, the signing side switches. Never the other way
around — a signature nobody can verify is worse than an old one everybody can.

## 10. Known gaps

- **A comma inside an attachment or `cc` entry** is ambiguous, because entries are joined with
  `,` after collapsing. Implementations should reject such entries at signing time. Not yet
  enforced.
- **The branch is not in the payload.** Two workspaces differing only by branch share a
  signature space. Branches are therefore a working tool, not a security boundary; a real
  second tenant gets its own repository.
- **One signer per action.** There is no threshold or second approver. For organisations where
  two people must agree, this protocol is not sufficient today.
- **The executor is trusted** to verify before acting. §7 detects violations after the fact; it
  cannot prevent them.
- **Timestamps are recorded, not enforced.** An approval does not expire.
