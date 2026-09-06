import json
import subprocess
from pathlib import Path

import pytest
from countersigned import Action, SoftwareKey, approve

WORKSPACE = "acme/office"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False), "utf-8")


@pytest.fixture
def repo(tmp_path) -> Path:
    """A business repository: a real git repo with a queued job and two actions —
    one countersigned, one not."""
    repo = tmp_path / "business"
    (repo / "app" / "jobs" / "queue").mkdir(parents=True)
    (repo / "app" / "jobs" / "done").mkdir(parents=True)
    (repo / "app" / "state").mkdir(parents=True)
    (repo / "secrets.env").write_text("TOKEN=never-read-this")

    write_json(repo / "app" / "jobs" / "queue" / "job-1.json", {
        "id": "job-1", "source": "app-chat", "prompt": "summarise the open actions",
        "agent": "office", "created_at": "2026-09-06T08:00:00Z", "status": "queued"})
    write_json(repo / "app" / "jobs" / "queue" / "job-2.json", {
        "id": "job-2", "source": "app-chat", "prompt": "later",
        "agent": "office", "created_at": "2026-09-06T09:00:00Z", "status": "queued"})

    key = SoftwareKey.generate()
    signed_action = Action(type="email", to="studio@example.com", subject="Offer",
                           attachments=[], body="Attached.")
    approval = approve(signed_action, key=key, workspace=WORKSPACE, action_id="go-signed",
                       device_id="iphone")
    write_json(repo / "app" / "state" / "gos.json", [
        {"id": "go-signed", "typ": "email", "an": "studio@example.com", "betreff": "Offer",
         "anhang": [], "text": "Attached.", "status": "approved",
         "freigabe": {"status": approval.status, "digest": approval.digest,
                      "nonce": approval.nonce, "at": approval.at,
                      "device_id": approval.device_id, "signature": approval.signature}},
        {"id": "go-open", "typ": "email", "an": "press@example.com", "betreff": "Statement",
         "anhang": [], "text": "No comment.", "status": "open"},
    ])
    write_json(repo / "app" / "state" / "devices.json", {
        "devices": [{"device_id": "iphone", "pubkey": key.public_key_b64,
                     "role": "owner", "name": "Phone"}],
        "roles": {"owner": ["email"]}})

    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "runner@example.com")
    git(repo, "config", "user.name", "Runner")
    git(repo, "remote", "add", "origin", f"https://github.com/{WORKSPACE}.git")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")
    return repo
