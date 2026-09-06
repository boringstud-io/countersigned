#!/usr/bin/env python3
"""A five-minute demo of countersigning, in a directory you can read.

No model runs here and nothing goes on the network. The interesting part is
not how an agent writes a draft — it is what has to be true before that draft
can leave the building.

    demo.py propose "send the offer to studio orange"
    demo.py sign go-0001
    demo.py verify go-0001
    demo.py execute go-0001 --consume
    demo.py audit

State lives in ./workspace as plain JSON, exactly as spec/DATA-CONTRACT.md
describes. Open it, edit it, break it — that is act three.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from countersigned import (Action, ActionRecord, Approval, Device, Registry, SoftwareKey,
                           VerificationError, approve, find_contradictions)

WORKSPACE_NAME = "acme/office"
HERE = Path(__file__).resolve().parent
STATE = HERE / "workspace" / "app" / "state"
KEY_FILE = HERE / "workspace" / "device.pem"
DEVICE_ID = "demo-laptop"

BOLD, DIM, RED, GREEN, YELLOW, OFF = "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[0m"
if not sys.stdout.isatty():
    BOLD = DIM = RED = GREEN = YELLOW = OFF = ""


# ---------------------------------------------------------------- state files

def read(name: str, default):
    path = STATE / name
    return json.loads(path.read_text("utf-8")) if path.exists() else default


def write(name: str, value) -> None:
    """Serialised the way the contract prescribes: indent 1, UTF-8, model order."""
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / name).write_text(json.dumps(value, indent=1, ensure_ascii=False), "utf-8")


def actions() -> list[dict]:
    return read("actions.json", [])


def action_by_id(action_id: str) -> dict:
    found = next((a for a in actions() if a["id"] == action_id), None)
    if found is None:
        die(f"no action {action_id!r} — run 'demo.py propose \"…\"' first")
    return found


def replace_action(updated: dict) -> None:
    write("actions.json", [updated if a["id"] == updated["id"] else a for a in actions()])


def as_action(record: dict) -> Action:
    return Action(type=record["typ"], to=record.get("an"), cc=record.get("cc", []),
                  subject=record.get("betreff"), attachments=record.get("anhang", []),
                  body=record.get("text", ""))


def device_key() -> SoftwareKey:
    """The simulated device.

    On a phone this key lives in the Secure Enclave and cannot be read by any
    process, including the app that uses it. Here it is a file. That difference
    is the difference between a demo and a deployment, and the demo says so
    every time it signs.
    """
    if KEY_FILE.exists():
        return SoftwareKey.from_pem(KEY_FILE.read_bytes())
    key = SoftwareKey.generate()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key.pem())
    write("devices.json", {
        "devices": [{"device_id": DEVICE_ID, "pubkey": key.public_key_b64,
                     "role": "owner", "name": "Demo laptop (software key)"}],
        "roles": {"owner": ["email"], "assistant": []}})
    return key


def registry() -> Registry:
    raw = read("devices.json", {"devices": [], "roles": {}})
    return Registry(
        devices=[Device(d["device_id"], d["pubkey"], d.get("role", ""), d.get("name", ""))
                 for d in raw["devices"]],
        roles=raw.get("roles", {}),
        used_nonces=set(read("nonces.json", [])))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def die(message: str) -> None:
    print(f"{RED}✗ {message}{OFF}")
    raise SystemExit(1)


# ------------------------------------------------------------------- act one

def cmd_propose(args) -> None:
    """An agent drafts. It may write anything here; it may send nothing."""
    existing = actions()
    action_id = f"go-{len(existing) + 1:04d}"
    record = {
        "id": action_id,
        "typ": "email",
        "an": args.to,
        "betreff": args.subject or args.intent.capitalize(),
        "anhang": args.attach,
        "text": args.body or (
            f"Hi,\n\n{args.intent} — the details are attached.\n\nBest regards"),
        "status": "open",
        "erstellt": now(),
        "vorschlag_von": "agent",
    }
    write("actions.json", existing + [record])

    canonical = as_action(record).canonical()
    # Kept so act three can show *which* line changed. The signature already
    # refuses a changed action without it; this is for the human reading along.
    proposals = read("proposals.json", {})
    proposals[action_id] = canonical
    write("proposals.json", proposals)

    print(f"{BOLD}{action_id}{OFF} drafted by the agent — status {YELLOW}open{OFF}")
    print(f"\n{DIM}the exact bytes a signature would cover:{OFF}")
    for line in canonical.splitlines():
        print(f"  {line}")
    print(f"\n{DIM}digest{OFF} {as_action(record).digest()}")
    print(f"\nNothing has been sent. {DIM}Try: demo.py execute {action_id} --consume{OFF}")


# ------------------------------------------------------------------- act two

def cmd_sign(args) -> None:
    record = action_by_id(args.id)
    key = device_key()
    status = "rejected" if args.reject else "approved"

    approval = approve(as_action(record), key=key, workspace=WORKSPACE_NAME,
                       action_id=record["id"], device_id=DEVICE_ID, status=status,
                       version=args.version)
    record["status"] = status
    record["freigabe"] = {
        "status": approval.status, "digest": approval.digest, "nonce": approval.nonce,
        "at": approval.at, "device_id": approval.device_id, "signature": approval.signature,
        "kanon_version": args.version,
    }
    replace_action(record)

    print(f"{YELLOW}⚠  simulated device: this key is a file on disk, not a Secure Enclave.{OFF}")
    print(f"   {DIM}On a phone the private half cannot be read by anything, including the app.{OFF}\n")
    print(f"{BOLD}{record['id']}{OFF} countersigned as "
          f"{GREEN if status == 'approved' else RED}{status}{OFF} "
          f"by {DEVICE_ID} (v{args.version})")
    print(f"  {DIM}signed bytes{OFF} "
          f"{approval.payload(args.version).decode()[:78]}…")
    print(f"  {DIM}signature{OFF}    {approval.signature[:44]}…")


def cmd_verify(args) -> int:
    record = action_by_id(args.id)
    freigabe = record.get("freigabe")
    if not freigabe:
        print(f"{RED}✗ {record['id']} carries no approval{OFF}")
        return 1

    approval = Approval(workspace=WORKSPACE_NAME, action_id=record["id"],
                        status=freigabe["status"], digest=freigabe["digest"],
                        nonce=freigabe["nonce"], at=freigabe["at"],
                        device_id=freigabe["device_id"], signature=freigabe["signature"])
    try:
        verdict = verify_now(record, approval)
    except VerificationError as exc:
        print(f"{RED}✗ {record['id']} does not verify:{OFF} {exc}")
        if "signature does not verify" in str(exc):
            explain_mismatch(record)
        return 1
    print(f"{GREEN}✓ {record['id']} verifies{OFF} — signed by "
          f"{verdict.device.name or verdict.device.device_id} "
          f"(role {verdict.device.role}, canonical v{verdict.version})")
    return 0


def verify_now(record: dict, approval: Approval):
    from countersigned import verify as _verify
    return _verify(as_action(record), approval, registry(),
                   workspace=WORKSPACE_NAME, action_id=record["id"])


def explain_mismatch(record: dict) -> None:
    """Say which line changed, if we still know what was proposed.

    A digest cannot be reversed, so this reads the proposal log — a convenience
    for the human, not part of the check. The signature had already refused.
    """
    was = read("proposals.json", {}).get(record["id"])
    if was is None:
        return
    now_lines, was_lines = as_action(record).canonical().splitlines(), was.splitlines()
    changed = [(b, a) for b, a in zip(was_lines, now_lines) if b != a]
    if not changed:
        return
    print(f"\n  {DIM}what changed after signing:{OFF}")
    for before, after in changed:
        print(f"    {RED}- {before}{OFF}")
        print(f"    {GREEN}+ {after}{OFF}")


def cmd_execute(args) -> int:
    record = action_by_id(args.id)
    if cmd_verify(args) != 0:
        print(f"{RED}✗ refusing to execute {record['id']}{OFF}")
        return 1
    if record["status"] != "approved":
        die(f"{record['id']} is {record['status']}, not approved")
    if not args.consume:
        print(f"\n{YELLOW}This would send. Nothing happens without --consume,{OFF}\n"
              f"{YELLOW}because executing burns the nonce and cannot be undone.{OFF}")
        return 0

    nonce = record["freigabe"]["nonce"]
    used = read("nonces.json", [])
    write("nonces.json", used + [nonce])
    log = read("send-log.json", {})
    log[record["id"]] = now()
    write("send-log.json", log)
    print(f"\n{GREEN}→ executed{OFF} (in a real system: sent). "
          f"nonce {nonce[:12]}… is now spent.")
    return 0


def cmd_audit(args) -> int:
    records, log = actions(), read("send-log.json", {})
    executed = set(log)
    mapped = []
    for record in records:
        freigabe = record.get("freigabe")
        valid = False
        if freigabe:
            approval = Approval(workspace=WORKSPACE_NAME, action_id=record["id"],
                                status=freigabe["status"], digest=freigabe["digest"],
                                nonce=freigabe["nonce"], at=freigabe["at"],
                                device_id=freigabe["device_id"],
                                signature=freigabe["signature"])
            try:
                verify_now(record, approval)
                valid = True
            except VerificationError:
                valid = False
        mapped.append(ActionRecord(action_id=record["id"], status=record["status"],
                                   has_valid_signature=valid,
                                   approved_at=(freigabe or {}).get("at")))

    findings = find_contradictions(mapped, send_log=log, executed=executed)
    if not findings:
        print(f"{GREEN}✓ nothing contradicts itself{OFF} "
              f"({len(records)} actions, {len(log)} sends)")
        return 0
    incidents = sum(f.is_incident for f in findings)
    for finding in sorted(findings, key=lambda f: not f.is_incident):
        colour = RED if finding.is_incident else YELLOW
        print(f"{colour}{finding}{OFF}")
    print(f"\n{DIM}{incidents} incident(s), {len(findings) - incidents} warning(s). "
          f"Signatures prove what was approved; this pass notices what happened anyway.{OFF}")
    return 1 if incidents else 0


def cmd_reset(args) -> None:
    import shutil
    if (HERE / "workspace").exists():
        shutil.rmtree(HERE / "workspace")
    print("workspace cleared")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="an agent drafts an action")
    p.add_argument("intent")
    p.add_argument("--to", default="studio-orange@example.com")
    p.add_argument("--subject")
    p.add_argument("--body")
    p.add_argument("--attach", nargs="*", default=["offer.pdf"])
    p.set_defaults(func=cmd_propose)

    p = sub.add_parser("sign", help="a human countersigns (simulated device)")
    p.add_argument("id")
    p.add_argument("--reject", action="store_true")
    p.add_argument("--version", type=int, default=3, choices=(3, 4))
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("verify", help="check the approval against the action as it is now")
    p.add_argument("id")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("execute", help="do it — verifies first, needs --consume")
    p.add_argument("id")
    p.add_argument("--consume", action="store_true")
    p.set_defaults(func=cmd_execute)

    sub.add_parser("audit", help="compare actions, approvals and the send log").set_defaults(
        func=cmd_audit)
    sub.add_parser("reset", help="delete the demo workspace").set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
