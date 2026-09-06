#!/usr/bin/env python3
"""Run one job from a repository's queue.

    python runner/run.py --repo ../your-business-repo --once
    python runner/run.py --repo ../your-business-repo --once --consume   # may execute approvals

The repository is an ordinary local clone. The runner writes only under app/,
never writes a decision, and verifies before it executes. What it did is on
stdout and, with --journal, in a JSONL file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentrunner.journal import Journal          # noqa: E402
from agentrunner.loop import oldest_job, run_job  # noqa: E402
from agentrunner.models import DEFAULT_MODEL, AnthropicModel  # noqa: E402
from agentrunner.tools import Tools              # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, type=Path,
                        help="path to a local clone of the business repository")
    parser.add_argument("--workspace", help="owner/repo the signatures are bound to; "
                                            "defaults to the origin remote")
    parser.add_argument("--once", action="store_true",
                        help="take exactly one job and stop — currently the only mode")
    parser.add_argument("--consume", action="store_true",
                        help="allow execute_action to spend a nonce")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--journal", type=Path, help="append JSONL here as well as stdout")
    args = parser.parse_args(argv)

    if not args.once:
        parser.error("only --once is implemented: this runner takes one job and stops. "
                     "Repeat it from cron or a workflow, so every cycle is a fresh process "
                     "with a fresh clone.")

    repo = args.repo.expanduser().resolve()
    workspace = args.workspace or _workspace_from_git(repo)
    journal = Journal(args.journal)

    found = oldest_job(repo)
    if found is None:
        journal.record("queue_empty", repo=str(repo))
        return 0
    job_path, job = found

    tools = Tools(repo=repo, journal=journal, workspace=workspace, consume=args.consume)
    model = AnthropicModel(args.model)
    cycle = run_job(job_path, job, tools, model, journal)

    still_queued = job_path.exists()
    journal.record("run_finished", job=cycle.job_id, turns=cycle.turns,
                   moved_to_done=not still_queued,
                   refusals=len(journal.events("refused")))
    return 1 if still_queued else 0


def _workspace_from_git(repo: Path) -> str:
    import subprocess
    result = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                            capture_output=True, text=True)
    url = result.stdout.strip()
    if not url:
        raise SystemExit("could not read the origin remote; pass --workspace owner/repo")
    tail = url.removesuffix(".git").replace(":", "/").split("/")
    return "/".join(tail[-2:])


if __name__ == "__main__":
    raise SystemExit(main())
