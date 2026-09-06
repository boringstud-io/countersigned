"""One cycle: take the oldest job, work it, record the result, move it, commit.

The model is behind a protocol with two implementations — the real API and a
scripted one for tests — because the interesting properties of this runner are
the refusals, and a refusal must be testable without a network or a bill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .journal import Journal
from .tools import Tools, dispatch

MAX_TURNS = 24

TOOL_SCHEMA: list[dict[str, Any]] = [
    {"name": "read_file", "description": "Read a text file anywhere in the repository.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "list_dir", "description": "List a directory in the repository.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": []}},
    {"name": "write_file",
     "description": "Write a file under app/. Anything else is refused. May never "
                    "set a status of approved or rejected, or write an approval.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"},
                                     "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "move_file", "description": "Move a file within app/.",
     "input_schema": {"type": "object",
                      "properties": {"source": {"type": "string"},
                                     "destination": {"type": "string"}},
                      "required": ["source", "destination"]}},
    {"name": "verify_action",
     "description": "Check that an action in app/state/gos.json carries a valid "
                    "countersignature. Required before execute_action.",
     "input_schema": {"type": "object", "properties": {"action_id": {"type": "string"}},
                      "required": ["action_id"]}},
    {"name": "execute_action",
     "description": "Carry out a countersigned action. Verifies first and spends "
                    "its nonce. Refused unless the run was started with --consume.",
     "input_schema": {"type": "object", "properties": {"action_id": {"type": "string"}},
                      "required": ["action_id"]}},
    {"name": "git_commit", "description": "Commit the changes under app/.",
     "input_schema": {"type": "object", "properties": {"message": {"type": "string"}},
                      "required": ["message"]}},
]

SYSTEM = """You are a job runner for a business's data repository.

You work one job at a time. The job's prompt says what is wanted. The repository
holds the state as JSON under app/.

Rules that are enforced, not merely requested — the tools will refuse you:
- You may write only under app/.
- You may never write a decision: no status of approved or rejected, no approval
  object. Those belong to a human's signed device. You prepare; they decide.
- To carry out an approved action you must call verify_action first. execute_action
  does it again anyway.

Finish by calling write_file to record the job's result and result_kurz, move_file
to move it from app/jobs/queue/ to app/jobs/done/, and git_commit once.

result is for the record: what you did, what you found, what you could not do.
result_kurz is one or two sentences addressed to the owner, in their language.
Say plainly when a source was thin or a step failed. Never claim you sent anything."""


class Model(Protocol):
    def respond(self, messages: list[dict], tools: list[dict], system: str) -> Any:
        """Return an object with .content (blocks) and .stop_reason."""


@dataclass
class Cycle:
    job_id: str
    turns: int = 0
    tool_calls: list[str] = field(default_factory=list)
    finished: bool = False
    text: str = ""


def oldest_job(repo: Path) -> tuple[Path, dict] | None:
    queue = repo / "app" / "jobs" / "queue"
    if not queue.is_dir():
        return None
    jobs = []
    for path in sorted(queue.glob("*.json")):
        try:
            jobs.append((path, json.loads(path.read_text("utf-8"))))
        except json.JSONDecodeError:
            continue
    if not jobs:
        return None
    return min(jobs, key=lambda pair: (pair[1].get("created_at") or "", pair[0].name))


def run_job(job_path: Path, job: dict, tools: Tools, model: Model,
            journal: Journal) -> Cycle:
    cycle = Cycle(job_id=job.get("id", job_path.stem))
    journal.record("job_started", job=cycle.job_id,
                   agent=job.get("agent", "-"), prompt=(job.get("prompt") or "")[:120])

    relative = job_path.relative_to(tools.repo).as_posix()
    messages: list[dict] = [{"role": "user", "content":
        f"Job file: {relative}\n"
        f"Job id: {cycle.job_id}\n"
        f"Agent: {job.get('agent', '-')}\n\n"
        f"{job.get('prompt', '')}"}]

    while cycle.turns < MAX_TURNS:
        cycle.turns += 1
        response = model.respond(messages, TOOL_SCHEMA, SYSTEM)
        blocks = list(response.content)
        messages.append({"role": "assistant", "content": blocks})

        calls = [b for b in blocks if getattr(b, "type", None) == "tool_use"]
        cycle.text = "\n".join(getattr(b, "text", "") for b in blocks
                               if getattr(b, "type", None) == "text").strip() or cycle.text
        if not calls:
            cycle.finished = True
            break

        results = []
        for call in calls:
            cycle.tool_calls.append(call.name)
            outcome = dispatch(tools, call.name, dict(call.input))
            results.append({"type": "tool_result", "tool_use_id": call.id,
                            "content": outcome.content, "is_error": outcome.is_error})
        messages.append({"role": "user", "content": results})

    if not cycle.finished:
        journal.record("gave_up", job=cycle.job_id, turns=cycle.turns,
                       reason=f"more than {MAX_TURNS} turns")
    journal.record("job_finished", job=cycle.job_id, turns=cycle.turns,
                   tools=",".join(cycle.tool_calls) or "-")
    return cycle
