# Ninety seconds

The script for the live version: what you say while `DEMO_PAUSE=1 ./demo.sh` runs. Timings are
from a real run — the commands take about eight seconds in total, so the rest is talking.

Terminal at 16pt or larger, window narrow enough that the canonical form does not wrap.

---

**Cold open (0:00–0:12)** — nothing on screen yet.

> Every demo of an AI agent ends the same way: it sends the email. I want to show you the
> other half — the part where it doesn't, and why that's the interesting half.

**Act 1 (0:12–0:35)** — run `propose`, then the failing `execute`.

> An agent drafted this. It could draft anything; that's not the hard part.
>
> [*point at the canonical form*] These lines are the whole action, in a fixed order. When
> someone approves it, this is what they approve — not a summary of it. There's no second
> version of the truth to disagree with the first.
>
> Now I tell it to send. [*run execute*] It won't. Not because of a policy, a prompt, or a
> guardrail the model could talk itself out of. There's no signature.

**Act 2 (0:35–1:05)** — `sign`, `verify`, `execute`, then `execute` again.

> Here's a human approving it. On a phone this is Face ID and a key in the Secure Enclave that
> nothing can read, not even the app. On my laptop it's a file — the demo says so, because I'm
> not going to pretend a laptop is a phone.
>
> [*point at the signed bytes*] That line is what gets signed. Protocol version, workspace,
> which action, the decision, the fingerprint of the content, a one-time number, the time, the
> device. Take it somewhere else and it stops verifying.
>
> Now it runs. [*run execute*] And now I run it again — same file, nothing changed.
> [*replay error*] Once. An approval is permission to do a thing, not permission to keep
> doing it.

**Act 3 (1:05–1:30)** — the `sed`, the failed verify, the audit.

> Last one. I'm going to edit the file after it was signed — change who it goes to. This is
> plain JSON in a Git repo, so of course I can.
>
> [*run verify*] Caught. And it tells me which line.
>
> But here's the honest bit. A signature proves something *was* approved. It cannot prove
> nothing *else* happened. So there's a second pass that compares what was approved against
> what actually went out. [*run audit*] This found a real one for us — a message that went out
> after it had been rejected. It didn't stop it. It noticed the same afternoon, and that's a
> different guarantee, and I'd rather say which one I have.

**Close (1:30)**

> Three hundred lines of Python, the spec is one file, it's Apache-2.0, and there's an iOS app
> that verifies the same signatures byte for byte. Link's on the last slide.

---

## If someone asks

**"Why not just an allow-list of tools?"** — That says which *kinds* of thing may happen. This
says which *specific* thing may happen, and proves it afterwards. An allow-list that permits
"send email" permits every email.

**"Isn't this just a confirmation dialog?"** — A dialog is a runtime check the same process can
skip; it leaves nothing behind. This leaves an artefact that a different program, on a
different machine, months later, can check without trusting the one that made it.

**"What if the agent changes the file after I sign?"** — Act 3.

**"What if it sends without asking at all?"** — Then nothing prevents it, and `audit` is what
you have. That's the boundary of the claim, and it's written down in the spec under "known
gaps" rather than left for someone to discover.

**"Does it need your app?"** — No. The app is one implementation of the signing side. The
protocol is a file, and there are two implementations that pass the same vectors.
