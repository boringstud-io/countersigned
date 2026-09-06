"""The tools a run may use. Five, deliberately.

Two fences, not one. The path fence says *where* a run may write. The decision
guard says *what* it may never write: a decision. Those are different rules and
a path check cannot express the second one — ``app/state/gos.json`` is a legal
path, and the approval field inside it is the one thing the runner must never
author.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from countersigned import Action, Approval, Device, Registry, VerificationError, verify

from .fence import Fence, FenceError
from .journal import Journal

MAX_READ_BYTES = 400_000
DECISION_FIELDS = ("status", "freigabe", "approval")
DECIDED = ("approved", "rejected")


class ToolError(Exception):
    """Refusal handed back to the model as a tool result, not raised further.

    A run that crashes on a refusal cannot report what it refused, and the
    report is the point.
    """


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


class Tools:
    def __init__(self, repo: Path, journal: Journal, workspace: str,
                 consume: bool = False) -> None:
        self.fence = Fence(repo)
        self.repo = self.fence.repo
        self.journal = journal
        self.workspace = workspace
        self.consume = consume

    # ------------------------------------------------------------- reading

    def read_file(self, path: str) -> str:
        target = self.fence.resolve_for_read(path)
        if not target.is_file():
            raise ToolError(f"no such file: {path}")
        data = target.read_bytes()
        if len(data) > MAX_READ_BYTES:
            raise ToolError(f"{path} is {len(data)} bytes; over the {MAX_READ_BYTES} limit")
        self.journal.record("read", path=path, bytes=len(data))
        return data.decode("utf-8", errors="replace")

    def list_dir(self, path: str = ".") -> str:
        target = self.fence.resolve_for_read(path)
        if not target.is_dir():
            raise ToolError(f"not a directory: {path}")
        names = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        self.journal.record("list", path=path, entries=len(names))
        return "\n".join(names) or "(empty)"

    # ------------------------------------------------------------- writing

    def write_file(self, path: str, content: str) -> str:
        target = self.fence.resolve_for_write(path)
        self._refuse_decisions(path, target, content)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.journal.record("wrote", path=path, bytes=len(content.encode()))
        return f"wrote {path} ({len(content.encode())} bytes)"

    def move_file(self, source: str, destination: str) -> str:
        src = self.fence.resolve_for_write(source)
        dst = self.fence.resolve_for_write(destination)
        if not src.is_file():
            raise ToolError(f"no such file: {source}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        self.journal.record("moved", **{"from": source, "to": destination})
        return f"moved {source} -> {destination}"

    def _refuse_decisions(self, path: str, target: Path, content: str) -> None:
        """The runner proposes; it never decides.

        Compares the incoming content against what is on disk and refuses if any
        record gains or changes a decision. A run that could write ``approved``
        would make every signature downstream meaningless — it could approve its
        own work and then satisfy the verifier's precondition itself.
        """
        if target.suffix != ".json" or not target.exists():
            before = []
        else:
            before = _records(json.loads(target.read_text("utf-8") or "null"))
        try:
            after = _records(json.loads(content or "null"))
        except json.JSONDecodeError:
            return  # not JSON we understand; the path fence already applied

        previous = {r.get("id"): r for r in before if isinstance(r, dict)}
        for record in after:
            if not isinstance(record, dict) or "id" not in record:
                continue
            old = previous.get(record["id"], {})
            for name in DECISION_FIELDS:
                new_value, old_value = record.get(name), old.get(name)
                if new_value == old_value:
                    continue
                if name == "status" and new_value not in DECIDED:
                    continue  # job states like queued/done are the runner's own
                self.journal.record("refused", tool="write_file", path=path,
                                    reason="would author a decision",
                                    record=record["id"], field=name, value=str(new_value))
                raise ToolError(
                    f"refused to write {path}: it would set {name}={new_value!r} on "
                    f"{record['id']}. Only a countersigned device may decide.")

    # ---------------------------------------------------------- verifying

    def verify_action(self, action_id: str) -> str:
        record, approval, action = self._load_action(action_id)
        if approval is None:
            self.journal.record("verify_failed", action=action_id, reason="no approval")
            raise ToolError(f"{action_id} carries no approval — it may not be executed")
        try:
            verdict = verify(action, approval, self._registry(),
                             workspace=self.workspace, action_id=action_id)
        except VerificationError as exc:
            self.journal.record("verify_failed", action=action_id, reason=str(exc))
            raise ToolError(f"{action_id} does not verify: {exc}") from exc
        self.journal.record("verified", action=action_id, device=verdict.device.device_id,
                            version=verdict.version)
        return (f"{action_id} verifies: signed by {verdict.device.device_id} "
                f"(role {verdict.device.role}, canonical v{verdict.version})")

    def execute_action(self, action_id: str) -> str:
        """Verify, then act. Both halves are required, in that order."""
        self.verify_action(action_id)
        if not self.consume:
            self.journal.record("refused", tool="execute_action", action=action_id,
                                reason="run was not started with --consume")
            raise ToolError(f"{action_id} verifies, but this run may not execute "
                            "(started without --consume)")
        record, approval, _ = self._load_action(action_id)
        nonces = self._read_json("app/state/nonces.json", [])
        if approval.nonce in nonces:
            self.journal.record("refused", tool="execute_action", action=action_id,
                                reason="nonce already spent")
            raise ToolError(f"{action_id}: nonce already spent (replay)")
        self._write_json("app/state/nonces.json", nonces + [approval.nonce])
        log = self._read_json("app/state/send-log.json", {})
        log[action_id] = _now()
        self._write_json("app/state/send-log.json", log)
        self.journal.record("executed", action=action_id, nonce=approval.nonce[:12])
        return f"{action_id} executed; nonce spent"

    def _load_action(self, action_id: str):
        records = self._read_json("app/state/gos.json", [])
        record = next((r for r in records if r.get("id") == action_id), None)
        if record is None:
            raise ToolError(f"no action {action_id}")
        action = Action(type=record.get("typ", ""), to=record.get("an"),
                        cc=record.get("cc", []), subject=record.get("betreff"),
                        attachments=record.get("anhang", []), body=record.get("text", ""))
        raw = record.get("freigabe") or record.get("approval")
        approval = None
        if raw:
            approval = Approval(workspace=self.workspace, action_id=action_id,
                                status=raw.get("status", ""), digest=raw.get("digest", ""),
                                nonce=raw.get("nonce", ""), at=raw.get("at", ""),
                                device_id=raw.get("device_id", ""),
                                signature=raw.get("signature", ""))
        return record, approval, action

    def _registry(self) -> Registry:
        raw = self._read_json("app/state/devices.json", {"devices": [], "roles": {}})
        return Registry(
            devices=[Device(d["device_id"], d["pubkey"], d.get("role", ""), d.get("name", ""))
                     for d in raw.get("devices", [])],
            roles=raw.get("roles", {}),
            used_nonces=set(self._read_json("app/state/nonces.json", [])))

    # ------------------------------------------------------------ commiting

    def git_commit(self, message: str) -> str:
        status = self._git("status", "--porcelain", "--", "app")
        if not status.strip():
            self.journal.record("nothing_to_commit")
            return "nothing to commit"
        # Only app/ is staged, even if something else in the tree changed —
        # the same rule as the write fence, enforced a second time at the door.
        self._git("add", "--", "app")
        self._git("commit", "-m", message)
        sha = self._git("rev-parse", "--short", "HEAD").strip()
        self.journal.record("committed", sha=sha, message=message)
        return f"committed {sha}"

    def _git(self, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(self.repo), *args],
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    # ------------------------------------------------------------- helpers

    def _read_json(self, relative: str, default):
        path = self.repo / relative
        if not path.exists():
            return default
        return json.loads(path.read_text("utf-8") or "null") or default

    def _write_json(self, relative: str, value) -> None:
        path = self.fence.resolve_for_write(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=1, ensure_ascii=False), "utf-8")


def _records(parsed) -> list:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("gos", "actions", "items"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return [parsed]
    return []


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dispatch(tools: Tools, name: str, arguments: dict) -> ToolResult:
    """Turn a tool call into a result. Refusals come back as results, not raises."""
    try:
        method = {
            "read_file": lambda: tools.read_file(arguments["path"]),
            "list_dir": lambda: tools.list_dir(arguments.get("path", ".")),
            "write_file": lambda: tools.write_file(arguments["path"], arguments["content"]),
            "move_file": lambda: tools.move_file(arguments["source"], arguments["destination"]),
            "verify_action": lambda: tools.verify_action(arguments["action_id"]),
            "execute_action": lambda: tools.execute_action(arguments["action_id"]),
            "git_commit": lambda: tools.git_commit(arguments["message"]),
        }[name]
    except KeyError:
        return ToolResult(f"no such tool: {name}", is_error=True)
    try:
        return ToolResult(method())
    except FenceError as exc:
        # The fence raises without journaling, so that it stays a pure function.
        tools.journal.record("refused", tool=name, reason=str(exc))
        return ToolResult(str(exc), is_error=True)
    except ToolError as exc:
        # Refusals with a rule behind them journal themselves, with the detail.
        return ToolResult(str(exc), is_error=True)
    except KeyError as exc:
        return ToolResult(f"{name} is missing argument {exc}", is_error=True)
