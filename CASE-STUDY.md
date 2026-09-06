# Nineteen days of countersigned actions

A small design gallery has run an AI agent on its actual business — mail, quotes, follow-ups —
since mid-August 2026. Every action that could reach someone outside the company required a
signature from the owner's phone first. This is what that produced, counted from the files.

The numbers below come from a private business repository. The commands that produced them are
in the footnotes: not so you can run them — you cannot — but so the person who wrote this can be
held to them, and so anyone evaluating the system under NDA can reproduce every figure rather
than take it on faith. No customer names, no message contents, no prices appear here.

## 1. What the business is

`spazio` — "a curated house for collectible design and more".[^1] One person, a few dozen
studios and makers, a shop, and the correspondence that comes with it. No engineering team. The
owner is the bottleneck for every decision, which is the ordinary condition of a small business
and the reason the experiment is worth anything.

## 2. The problem the agent was pointed at

Not "write my emails". The problem was that a competent assistant would need to read the inbox,
know the pipeline, draft the reply, and then **stop** — because the one thing nobody sane
delegates is the send button.

Every automation available in 2026 solves the first three and finesses the fourth: a
confirmation dialog, an "are you sure", a human-in-the-loop checkbox. All of these are runtime
checks by the same process that wants to proceed, and none of them leaves anything behind. A
week later there is no way to answer *what exactly did I approve, and did it change afterwards?*

## 3. What the agent does, and what it may not

The agent runs on a schedule against a Git repository of plain JSON. It reads mail, keeps a
pipeline, drafts replies, prepares quotes, asks questions, and writes everything it does back
into that repository.

It may not send. It has no mail tool, no publish tool, no shop tool. What it produces instead is
an *action card*: recipient, subject, attachments, body. The owner sees the card on a phone and
either signs it or does not. The signature is made in the Secure Enclave, covers the exact
content in a canonical form, and carries a one-time number. Only then does a separate step
verify the signature and carry the action out.

The full mechanism is in [`spec/PROTOCOL.md`](spec/PROTOCOL.md); the five-minute version is in
[`examples/`](examples/README.md).

## 4. The numbers

Period: **17 August to 5 September 2026 — 19 days** of signed operation.[^2] The repository
itself is older (54 days); signatures start on 17 August.

| | |
|---|---|
| agent runs | **182**[^3] |
| action cards created | **116** |
| — approved | **103** |
| — rejected | **7** |
| — still open | **6**[^4] |
| cards carrying a signature | **104** |
| actions actually executed | **90** |
| approvals whose signature verifies today | **100 of 104**[^5] |
| — under the current canonical form (v3) | **80** |
| — under earlier versions (v2, v1) | **12, 8** |
| — that do not verify | **4** |
| one-time numbers spent | **89**, all distinct[^6] |
| **replays** | **0** |
| questions the agent asked the owner | **159**, of which 153 answered |
| mail threads handled | **47**, 18 with a drafted reply |
| **sends recorded without any signature** | **0**[^7] |

Two of those rows deserve their qualifications rather than a footnote nobody reads.

**"0 sends without a signature" is provable for part of the period, not all of it.** An
independent send index exists only from 31 August; it holds 50 entries and every one of them
belongs to a signed, approved card. Before that date the only record of a send is the card's own
field, written by the same side that sends — which is exactly the kind of evidence this project
exists to distrust. The honest claim is: *for the 50 sends we can check independently, zero were
unauthorised. For the earlier 40, we have the agent's word.*

**"4 approvals do not verify" is not a rounding error.** One was signed before the workspace
binding existed and cannot be recomputed by any current implementation — the system says so
rather than calling it invalid, which took a correction to get right. Three carry a decided
status with no signature at all: they were written by the automation side rather than by the
signing app. That is the next section.

## 5. The incident, and the thing that was built because of it

**25 August 2026.** A card carrying the owner's *signed rejection* also carried a send
timestamp. The message had gone out at 07:43 UTC. He learned about it from the agent's own
report, not from the app.

Nothing about the signature had failed. The rejection was valid and is still valid today. What
failed is the assumption underneath every scheme like this one: that proving *what was approved*
is the same as knowing *what happened*. It is not. A signature is a statement about a decision.
It says nothing about the world.

The contradiction had been sitting in data the app already synchronised. Nobody had looked.

So a second pass was built — deliberately on the *other* side, in the app, not in the automation
that had produced the incident: compare the actions, the approvals, and whatever actually sent,
and report every place they disagree. It runs on every refresh. Against the current state it
finds five things: the one incident above, and four sends whose approval cannot be proven.[^8]

That pass prevents nothing. It noticed the 25 August case the same afternoon, and it is the
reason the four unprovable sends are a number in this document instead of a surprise. Detection
is a weaker guarantee than prevention. It is also the one that can be honestly offered, and
saying which one you have is most of the argument.

## 6. What is still open

- **`cc` is not covered by the deployed signature.** The canonical form has five lines; a copied
  recipient is not one of them, so an approval does not cover who else receives the message.
  Found on 5 September while extracting the protocol into this repository — before it could be
  used, and checked: no action in the whole period ever carried a `cc`. Version 4 of the
  canonical form adds it. Both implementations here verify v4 today; the deployed verifier does
  not yet, and the signing side switches only after it does.
- **One signer.** There is no second approver and no threshold. For a business of one that is
  the right shape. For anything larger it is a missing feature, not a philosophy.
- **The executor is trusted to verify.** It runs on the side that can also send. Section 5 is
  what that costs.
- **Approvals do not expire.**

The full list, with the reasoning for each, is in [`SECURITY.md`](SECURITY.md) and
[`spec/PROTOCOL.md` §10](spec/PROTOCOL.md#10-known-gaps).

## What this is evidence for

Not that the agent is clever. Its drafts are ordinary and its judgment is average.

The claim is narrower and, for anyone putting an agent near a customer, more useful: **a
business ran on agent-prepared actions for nineteen days, and every action that reached the
outside world can be traced to a specific human decision over specific content on a specific
device — or is on a list of four that cannot, published here.**

That list is the point. A system that produces no such list is not safer; it is just quieter.

---

[^1]: `app/state/business.json`, field `tagline`.
[^2]: First and last approval timestamp: `jq -r '[.[]|select(.approval)|.approval.at]|sort|(first,last)' app/state/gos.json`
[^3]: `jq .lauf_nr app/state/system.json` (182). Independently, `git log --oneline | grep -ci 'stunden-lauf'` counts 206 hourly-run commits; the run counter starts later than the commits.
[^4]: `jq -r '[.[]|.status]|group_by(.)|map({(.[0]):length})|add' app/state/gos.json`
[^5]: Verified by running the Swift implementation in this repository over the real `gos.json` and `devices.json`: 80 v3, 12 v2, 8 v1, 4 failures. The same 80 v3 figure comes out of the Python implementation, and out of the iOS app after it was rewired to use this package — three independent paths, same number.
[^6]: `wc -l < app/state/go-nonces.log` (89) versus `cut -d'|' -f1 app/state/go-nonces.log | sort -u | wc -l` (89). Equal means no nonce was ever accepted twice.
[^7]: Every entry in `app/state/versand_index.json` (50, dated 31 Aug – 5 Sep) resolves to a card with `status == "approved"` and a non-empty `approval`. Checked by script, not by eye.
[^8]: One rejected-and-sent (25 Aug), four sent-without-provable-approval (18 Aug, 19 Aug, 24 Aug, 29 Aug). Card identifiers withheld; they name customers.
