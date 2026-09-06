# The minimal runner

A job runner that verifies before it acts. About 700 lines, no framework, no queue, no
database — one process takes one job from a Git repository, works it, writes the result back
and stops.

It exists to answer one question: does the protocol in [`spec/`](../spec/PROTOCOL.md) need a
particular agent platform? It does not. This runner is a plain script against the Anthropic
Messages API, and the same signed approvals verify the same way.

```bash
pip install ./python anthropic
python runner/run.py --repo ../your-business-repo --once
python runner/run.py --repo ../your-business-repo --once --consume   # may spend a nonce
```

`--repo` is an ordinary local clone. `--workspace owner/repo` is read from the `origin` remote
unless you pass it; it must match what the signatures are bound to, or nothing verifies.

## What it may do

| tool | fence |
|---|---|
| `read_file`, `list_dir` | anywhere inside the repository, nowhere outside it |
| `write_file`, `move_file` | **only under `app/`**, after resolving symlinks and `..` |
| `verify_action` | checks a countersignature against the action as it is *now* |
| `execute_action` | verifies first; refused unless the run was started with `--consume` |
| `git_commit` | stages `app/` only, even if something else in the tree changed |

## The two fences

A path fence says *where* a run may write. It cannot say *what* it may never write, because
`app/state/gos.json` is a perfectly legal path and the approval field inside it is the one
thing a runner must never author. So there is a second check on content: a write that would
set a status to `approved` or `rejected`, or add an approval object, is refused and recorded.

Without it the whole scheme is decorative — a runner that can write `approved` can approve its
own work and then satisfy the verifier's precondition itself.

```
✗ refused tool=write_file path=app/state/gos.json reason=would author a decision record=go-open field=status value=approved
```

Job states are different and allowed: `queued` → `done` is the runner's own bookkeeping. Only
the two decision words are reserved.

## The journal

Every read, write, refusal, verification and commit goes to stdout and, with `--journal
run.jsonl`, to a file. A refusal that leaves no trace is indistinguishable from an action that
never happened, and the runner's guarantees are mostly refusals.

## Running it in CI

[`example-workflow/runner.yml`](example-workflow/runner.yml) goes in the *business*
repository. One cycle per run, in a fresh checkout, with `concurrency` set so two cycles
cannot both take the oldest job. `--consume` is a manual input, not a default: a scheduled run
that may spend nonces is a scheduled run that may act unattended.

## What it is not

No connectors — no mail, no shop, no calendar. The runner proves the loop, not the reach.
No multi-tenancy, no billing, no supervision. One repository, one job, one process, then exit.

That is not a roadmap being deferred. A runner that holds state between cycles accumulates
assumptions, and an assumption is exactly the thing a verifier cannot check.

## Tests

```bash
cd runner && PYTHONPATH=tests python -m pytest tests -q
```

25 tests, none of which need a network or an API key: the model sits behind a two-method
protocol, and the tests script it. What they assert is what the *tools* did — every escape
route out of `app/`, every way to author a decision, verify against a tampered action, replay
a spent nonce, and a commit that stages more than it should.
