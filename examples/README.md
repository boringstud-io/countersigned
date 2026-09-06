# The five-minute demo

Three commands, one directory, no account. What it shows is not that an agent can write an
email — everything can write an email. It shows what has to be true before that email is
allowed to leave.

```bash
git clone https://github.com/boringstud-io/countersigned
cd countersigned/examples
./demo.sh
```

Needs Python 3.10+ and, the first time, the network — it makes a virtualenv and installs
`cryptography`. Nothing else: no server, no API key, no model. `DEMO_PAUSE=1 ./demo.sh` waits
for a keypress between acts, which is what you want in front of people.

The output below is the real run, pasted unedited.

## Act 1 — the agent proposes, and cannot send

The agent may write anything. Writing is not sending.

```
$ .venv/bin/python demo.py propose "send the offer to studio orange"
go-0001 drafted by the agent — status open

the exact bytes a signature would cover:
  typ=email
  an=studio-orange@example.com
  betreff=Send the offer to studio orange
  anhang=offer.pdf
  text=Hi,
  
  send the offer to studio orange — the details are attached.
  
  Best regards

digest 7ade1482c0f2f212c0824ee52834e0a8aff7552aba040e5fb5a63cb5a4fc5faf

Nothing has been sent. Try: demo.py execute go-0001 --consume
$ .venv/bin/python demo.py execute go-0001 --consume
✗ go-0001 carries no approval
✗ refusing to execute go-0001
```

Two things to notice. The canonical form is printed in full: those exact bytes, in that exact
order, are what a signature covers — there is no separate "summary of what you approved" that
could disagree with the thing itself. And the execute attempt fails on the only ground that
matters, that nobody has signed it.

## Act 2 — a human countersigns, and it runs once

```
$ .venv/bin/python demo.py sign go-0001
⚠  simulated device: this key is a file on disk, not a Secure Enclave.
   On a phone the private half cannot be read by anything, including the app.

go-0001 countersigned as approved by demo-laptop (v3)
  signed bytes nino-go-v3|acme/office|go-0001|approved|7ade1482c0f2f212c0824ee52834e0a8aff755…
  signature    MEUCIDT9vDn4ui0SnxmyPnAByXjpkEEn6V1Vw4t6Jcge…
$ .venv/bin/python demo.py verify go-0001
✓ go-0001 verifies — signed by Demo laptop (software key) (role owner, canonical v3)
$ .venv/bin/python demo.py execute go-0001 --consume
✓ go-0001 verifies — signed by Demo laptop (software key) (role owner, canonical v3)

→ executed (in a real system: sent). nonce ae3be6c2ef76… is now spent.

   …and a second time:
$ .venv/bin/python demo.py execute go-0001 --consume
✗ go-0001 does not verify: nonce already used (replay)
✗ refusing to execute go-0001
```

The signed bytes are printed too, because they are not a secret: they bind the protocol
version, the workspace, the action id, the decision, the digest, a nonce, the time and the
device. Take that approval to another workspace or another action and it stops verifying —
the values it names are checked against the ones the caller is actually holding.

The second `execute` is the point of the nonce. An approval authorises one execution, not a
standing permission. Nothing in the file changed between the two runs; the nonce was spent.

## Act 3 — someone edits the file afterwards

```
$ sed s/studio-orange/competitor/ workspace/app/state/actions.json
$ .venv/bin/python demo.py verify go-0001
✗ go-0001 does not verify: signature does not verify for any accepted version

  what changed after signing:
    - an=studio-orange@example.com
    + an=competitor@example.com

   And an action that was never approved, but shows up as sent:
$ .venv/bin/python demo.py audit
[incident] go-0002: Not decided yet — but it was sent on 2026-09-06T09:04:00+00:00
[warning] go-0001: Sent on 2026-09-06T08:23:31+00:00 without a verifiable approval

1 incident(s), 1 warning(s). Signatures prove what was approved; this pass notices what happened anyway.

The state is plain JSON in ./workspace — read it, break it, run audit again.
```

The edit is an ordinary text edit — the state is JSON in a Git repo, so anyone with write
access can do it, and that is deliberate. The signature is what makes it detectable rather
than prevented. `verify` refuses on the digest alone; the line-level diff underneath is read
from a proposal log and is a courtesy to the human reading the output, not part of the check.

The last part is the half that signatures cannot do. A signature proves that an action was
approved. It cannot prove that nothing else happened. `audit` compares three sources — the
actions, the approvals and whatever actually sent — and reports where they disagree. In the
production system this pass found a real incident: a message that went out after it had been
rejected. It did not prevent it. It noticed, the same afternoon.

## Then break it yourself

```bash
cat workspace/app/state/actions.json      # the actions
cat workspace/app/state/devices.json      # who may sign what
cat workspace/app/state/nonces.json       # what has been spent
./demo.py audit
```

Change a subject, delete an approval, invent a send-log entry, sign with `--reject` and then
try to execute. The checks are in `python/countersigned/`, about 300 lines, and the rules they
implement are written down in [spec/PROTOCOL.md](../spec/PROTOCOL.md).

## What the demo is not

The device key here is a **file on disk**. On a phone it lives in the Secure Enclave, cannot be
read by any process including the app that uses it, and is released only by Face ID. The demo
says so every time it signs, because a demo that quietly implies hardware it does not have is
worse than no demo.

There is also no model in this loop. Which agent drafts the action, and how well, is a
different problem from whether it may act — and keeping them separate is most of the argument.
