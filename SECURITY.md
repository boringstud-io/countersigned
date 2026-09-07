# Security

This document says what the protocol in [`spec/PROTOCOL.md`](spec/PROTOCOL.md) is for, what it
does not do, and how to report a problem. The mechanical gaps are listed in
[§10 of the protocol](spec/PROTOCOL.md#10-known-gaps); this is the policy around them.

The short version: **a signature proves that a particular human approved a particular action on
a particular device. It proves nothing about whether that action was a good idea, and it cannot
stop a system that never asks.**

## 1. What the protocol guarantees

Given a correct implementation and a device key the attacker does not hold:

- **An action cannot be executed without an approval** that verifies against the registry.
- **The approval covers the content**, not a description of it. Recipient, subject,
  attachments and body are hashed in a fixed canonical form. Change any of them after signing
  and verification fails.
- **An approval authorises one execution.** The nonce is recorded when it is spent; a second
  attempt is refused as a replay.
- **An approval is bound to its workspace and its action id.** Both are inside the signed
  bytes *and* are compared against the caller's own context — an approval lifted from another
  repository, or from another action in the same one, does not verify.
- **A changed device key invalidates that device** until a human confirms it. Key replacement
  and device restore look identical to an attacker swapping a key, so both stop the line.
- **Verification is side-effect free.** Checking is separate from consuming, so a verifier can
  be run by anyone, at any time, without changing anything.
- **The proof outlives the tool.** An approval is a text payload plus a signature plus a public
  key. Any program, in any language, years later, can check it without trusting the one that
  made it.

## 2. What it does not guarantee

This section matters more than the one above. If you take one thing from this document, take
this one.

- **It does not make the agent correct.** Nothing here judges whether an action should happen.
  A human approving a bad draft produces a valid signature over a bad action.
- **It does not prevent a system from acting outside the protocol.** If something can send mail
  and chooses not to ask, no signature scheme stops it. §7 of the protocol compares what was
  approved against what actually went out and *reports* the difference. Detection is a weaker
  guarantee than prevention, and it is the one on offer. It is also the one that found a real
  incident on 2026-08-25 — a message that went out after it had been rejected.
- **It does not make the executor honest.** The side that verifies is usually the side that can
  also send. A compromised executor can skip verification entirely. What it cannot do is
  produce a signature that a *third party* will accept — which is why the audit pass runs from
  the records rather than from the executor's own claims.
- **It does not authenticate the person, only the device.** Whoever holds the unlocked device
  can approve. Face ID and the Secure Enclave raise the bar; they are not identity.
- **Approvals do not expire.** An approval signed in March verifies in December if its nonce
  was never spent. Freshness is the caller's problem.
- **One signature is enough.** There is no second approver and no threshold. If your rules
  require two people to agree, this protocol does not implement your rules.

## 3. Known weaknesses we are living with

Each one says why, because a list without reasons is a list nobody acts on.

| weakness | why it is still open |
|---|---|
| **`cc` is not covered in v3** (the deployed version). v4 adds it. | Found 2026-09-05 during extraction. No production action has ever carried a `cc` — checked, not assumed — so nothing is currently exposed. v4 is specified and both implementations here verify it; the deployed verifier does not yet, and the signing side switches only after it does. Reading side before writing side, always. |
| **The branch is not in the payload.** Two branches of one repository share a signature space. | Making the branch part of the payload would break every existing signature for a boundary that should not exist anyway. Branches are a working tool; a real second tenant gets its own repository. Stated so nobody builds a permission model on branches. |
| **A comma inside a `cc` or attachment entry is ambiguous.** | Entries are joined with `,`. The fix is to reject such entries when signing, which no implementation here does yet. Email addresses cannot contain a bare comma, so the reachable case today is a filename. |
| **A lost device stays in the registry** until someone removes it by hand. | The key is gone with the device, so nobody can sign with it — the entry is stale, not dangerous. Automatic expiry would need a clock nobody controls and would lock out a user whose phone was merely off. |
| **The nonce log is a file the executor writes.** An executor that does not record a spent nonce enables a replay. | The log lives in the same repository, so an unrecorded execution is visible in the audit pass as a send without a matching consumed nonce. It is detection again, not prevention. |
| **No revocation list for approvals.** Once signed, an approval stands until executed or deleted. | Deleting the action is the revocation. Adding a second mechanism would create two sources of truth about the same decision. |

## 4. Threat model

What we assume an attacker can do: read the repository, write to the repository, run code on
the executing machine. What we assume they cannot do: extract a private key from a Secure
Enclave, or forge a P-256 signature.

| the attacker | what they achieve | what stops or catches it |
|---|---|---|
| **Edits an action after it was approved** — changes the recipient, adds an attachment | Nothing. | Verification fails on the digest. This is the case the canonical form exists for. |
| **Copies a valid approval onto a different action**, or into another workspace | Nothing. | The workspace and action id are in the signed bytes and are compared against the caller's context. |
| **Replays an executed approval** | Nothing, if the nonce log is intact. | The nonce is refused on the second use. If the log was lost, the audit pass shows an execution without a matching record. |
| **Holds the unlocked device** | Everything that person could do. | Nothing in this protocol. Device security is the boundary. |
| **Compromises the executor** and sends without verifying | The message goes out. | Not prevented. The audit pass reports a send with no valid approval — usually within one cycle. This is the residual risk, and it is the honest headline. |
| **Registers a device of their own** in the registry | Everything, immediately. | Nothing in this protocol. **The registry is as trusted as the repository's write access.** Protect it like a credential: branch protection, review on changes to the device list. |
| **Steals an automation token** that can start agent runs | Can make the agent work, draft, and prepare — not send. | The protocol holds: a run without a signature reaches nothing outside. But it can burn money and fill the workspace. Rotate such tokens; they are out of this protocol's scope. |
| **Uses a capability the environment was never meant to have** | Whatever that capability allows. | Nothing in this protocol — and this is the case people get wrong. An environment that *should not* send is not the same as one that *cannot*. A real instance: an agent run whose environment was deliberately specified with no send surface turned out to carry a mail connector with an unrestricted tool list, because that list is fixed when the run is created and cannot be narrowed afterwards. Nothing was sent; the instructions forbade it. But instructions are not a boundary. **Check what a run can do, not what it is told to do — and check it at creation, because that is the only moment it can be changed.** |

**Out of scope for this repository:** the product that produces these signatures, the agent that
drafts the actions, and any particular tenant's automation. Reports about those belong to their
own projects.

## 5. Reporting

Use **GitHub's private vulnerability reporting** on this repository (Security → Report a
vulnerability). Please do not open a public issue for a suspected vulnerability.

What to expect:

- **Acknowledgement within 72 hours.** This is a small project — that is a promise about
  answering, not about fixing.
- An assessment of whether it affects the protocol (the specification), an implementation, or
  neither, and a fix or a documented gap for the first two.
- Credit in the release notes if you want it.

If you find that this document is wrong — that something in §1 does not actually hold — that is
the report we most want to receive.
