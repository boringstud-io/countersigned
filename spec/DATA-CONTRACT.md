# The data contract

The protocol in [PROTOCOL.md](PROTOCOL.md) signs actions. This document describes the files
those actions live in — the contract between an agent that writes and an app that reads.

It is deliberately boring: plain JSON files in a Git repository. That choice buys three things
that a database does not — every change has an author and a timestamp, any tool can read it,
and the owner can walk away with `git clone`.

## Ownership: who may write which field

The hardest rule in a two-writer system is not *how* to write, it is *what*. Every field
belongs to exactly one side:

| written by | examples |
|---|---|
| **the agent** | the action itself: id, type, recipient, subject, body, attachments; a task's steps (`id`, `text`); results, summaries, notes |
| **the human's app** | decisions: `status`, the approval object, `snoozed_until`, a step's `done` / `done_at`, answers |

Neither side rewrites the other's fields. This is what makes concurrent work safe without
locking: the agent adds a step while the human ticks another, and both survive.

## The rule that costs data if ignored

**A writer must preserve fields it does not know.**

The reference app writes whole lists back through its model. A field the model does not know is
silently dropped on the next write — not by malice, by serialisation. This was measured on
2026-08-31: fields the agent had added disappeared on the human's next tap, and nobody noticed
until the agent looked for them.

Two consequences for any implementation:

1. Model every field of the contract explicitly, including ones you do not use.
2. When adding a field, the *reading* side ships first and the *writing* side second — the same
   ordering as the protocol cutover, for the same reason.

A test that writes an unknown field, performs an unrelated update, and asserts the field is
still there is worth more than the rest of the suite.

## Serialisation

Both sides write the same shape, so a diff shows the change and not the formatting:

- UTF-8, unescaped (no `\uXXXX` for non-ASCII, no escaped slashes)
- indent = 1 space, no trailing newline
- **field order is model order**, not alphabetical

The last point needs a custom encoder in most languages. Alphabetical ordering re-sorts the
agent's file on every human write, turning a one-line change into a whole-file diff and every
merge into a conflict. Hash-order — the default in some standard libraries — is worse: it
differs between processes, so two identical writes produce different bytes.
— `KanonischSchreiber.swift`

## Merge behaviour

Writes are applied to the **freshly fetched** state, never to a cached copy:

1. fetch the current file
2. apply the single change (one action, one field)
3. write back with the fetch's version identifier; on conflict, repeat

An empty or unreadable fetch is an **abort**, not a reason to fall back to the local copy. A
local copy that is a subset of the truth will otherwise recreate the file without the entries
it never saw — measured, and the reason this paragraph exists.

## Reading defensively

The agent writes prose-shaped data; it will eventually write something unexpected. The reading
side must degrade per entry, not per file:

- an unknown enum value keeps its raw string and renders as itself — it never turns into a
  default that means something else
- one unreadable entry in a list drops that entry, not the list, and the reader reports that it
  did (silently showing 49 of 50 items is worse than showing an error)
- a field that is a string where an object was expected is a typo, not a crash

## Files

The reference implementation uses one directory of state files (actions, questions, plan,
devices, roles, nonce log, send log) plus a job queue. Their exact names are implementation
detail; what is contractual is the ownership rule, the serialisation, and the merge behaviour
above.
