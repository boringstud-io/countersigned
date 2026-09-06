# Contributing

Thanks for looking. This is a small project with one maintainer, so here is what will and will
not happen, stated up front rather than discovered in a stale pull request.

## What this project is

A specification and two implementations of it. **The specification is the product.** The code
exists to prove the specification is implementable and to be usable; if the two ever disagree,
the specification is what gets fixed first.

That shapes everything below.

## The rules that are not negotiable

1. **A protocol change needs a vector.** Anything that alters the canonical form, the digest, or
   the payload must add a case to [`vectors/vectors.json`](vectors/vectors.json), which both
   test suites read from the same file. A change that only one implementation can demonstrate is
   not a change, it is a fork.
2. **Existing signatures keep verifying.** Real approvals exist, made by a real person, over
   real decisions. A change that invalidates them is a new version of the canonical form, with a
   number, alongside the old one — never an edit to an existing one.
3. **Reading side before writing side.** A new version must be *accepted* by every verifier
   before anything *produces* it. Reverse that order and you make somebody's genuine approval
   unverifiable. This has nearly happened twice; both times are written up in the protocol.
4. **No cryptography of our own.** P-256, SHA-256, DER, via the platform library. If a change
   needs a new primitive, that is a discussion before it is a patch.

## What is likely to be accepted

- A test that fails against the current code and should not.
- A case in `SECURITY.md` §3 or §4 that is missing. This is the most valuable thing you can send.
- A third implementation, in any language, that passes the vectors unchanged. Say so in an issue
  first so it can be linked rather than vendored.
- Clearer wording in `spec/`, especially where a rule states an intent instead of an operation —
  that distinction has cost a valid approval once already.
- Anything that makes the demo shorter or plainer.

## What is unlikely to be accepted

- A framework, a plugin system, or an abstraction with one implementation behind it.
- Multi-tenancy, hosting, billing, a web UI, a queue. Deliberately out of scope; see
  [`runner/README.md`](runner/README.md) for why the runner stays small.
- A dependency, unless it removes more code than it adds.
- Renaming the German field keys in the canonical form. They are part of the signed bytes, so
  renaming them would change every digest ever produced. This is explained in the spec and is
  not an oversight.

## Practical

- Run the suites before opening a PR: `python -m pytest python/tests -q`, `swift test`, and
  `cd runner && PYTHONPATH=tests python -m pytest tests -q`. CI runs all three plus the demo.
- Keep commit messages about *why*. The repository's history is meant to be readable as an
  argument, not a changelog.
- One concern per pull request.

## Security

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability
reporting on this repository; [`SECURITY.md`](SECURITY.md) says what to expect.
