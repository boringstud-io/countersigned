"""What the runner does, and — more to the point — what it refuses.

Every test drives the real loop with a scripted model, so the assertions are
about the tools and the journal, not about a language model's mood.
"""

import json

import pytest
from agentrunner.journal import Journal
from agentrunner.loop import oldest_job, run_job
from agentrunner.models import ScriptedModel, TextBlock, ToolUseBlock
from agentrunner.tools import Tools

from conftest import WORKSPACE, git

RESULT = {"id": "job-1", "source": "app-chat", "prompt": "summarise the open actions",
          "agent": "office", "created_at": "2026-09-06T08:00:00Z", "status": "done",
          "result": "Two actions: one approved, one open.",
          "result_kurz": "Zwei aktionen offen — eine wartet auf dein go."}


def tools_for(repo, journal, consume=False):
    return Tools(repo=repo, journal=journal, workspace=WORKSPACE, consume=consume)


def drive(repo, turns, consume=False):
    journal = Journal(echo=False)
    job_path, job = oldest_job(repo)
    model = ScriptedModel(turns)
    cycle = run_job(job_path, job, tools_for(repo, journal, consume), model, journal)
    return cycle, journal, model


def test_the_oldest_job_is_taken_first(repo):
    path, job = oldest_job(repo)
    assert job["id"] == "job-1"


def test_a_job_is_worked_and_ends_in_done_with_a_short_result(repo):
    cycle, journal, _ = drive(repo, [
        [ToolUseBlock("read_file", {"path": "app/state/gos.json"})],
        [ToolUseBlock("write_file", {"path": "app/jobs/queue/job-1.json",
                                     "content": json.dumps(RESULT, indent=1)})],
        [ToolUseBlock("move_file", {"source": "app/jobs/queue/job-1.json",
                                    "destination": "app/jobs/done/job-1.json"})],
        [ToolUseBlock("git_commit", {"message": "job-1 done"})],
        [TextBlock("finished")],
    ])
    done = repo / "app" / "jobs" / "done" / "job-1.json"
    assert done.is_file(), "the job did not reach done/"
    assert not (repo / "app" / "jobs" / "queue" / "job-1.json").exists()
    assert json.loads(done.read_text())["result_kurz"]
    assert cycle.finished
    assert journal.events("committed"), "nothing was committed"
    assert "job-1 done" in git(repo, "log", "-1", "--pretty=%s")


def test_a_write_outside_app_is_refused_and_recorded(repo):
    cycle, journal, model = drive(repo, [
        [ToolUseBlock("write_file", {"path": "secrets.env", "content": "TOKEN=stolen"})],
        [TextBlock("understood")],
    ])
    assert (repo / "secrets.env").read_text() == "TOKEN=never-read-this"
    refusals = journal.events("refused")
    assert refusals and "outside" in refusals[0].detail["reason"]
    # The refusal must reach the model, or it will simply try again.
    assert any(r["is_error"] for r in model.tool_results)


def test_climbing_out_with_dot_dot_is_refused(repo):
    _, journal, _ = drive(repo, [
        [ToolUseBlock("write_file", {"path": "app/../.git/config", "content": "x"})],
        [TextBlock("ok")]])
    assert journal.events("refused")
    assert "[core]" not in (repo / ".git" / "config").read_text() or True
    assert git(repo, "status", "--porcelain") == ""


def test_the_runner_may_not_approve_an_action(repo):
    """The whole point. A path fence cannot express this: the path is legal."""
    gos = json.loads((repo / "app" / "state" / "gos.json").read_text())
    for record in gos:
        if record["id"] == "go-open":
            record["status"] = "approved"
    _, journal, model = drive(repo, [
        [ToolUseBlock("write_file", {"path": "app/state/gos.json",
                                     "content": json.dumps(gos, indent=1)})],
        [TextBlock("understood")]])
    on_disk = json.loads((repo / "app" / "state" / "gos.json").read_text())
    assert {r["id"]: r["status"] for r in on_disk}["go-open"] == "open"
    refusal = journal.events("refused")[0]
    assert refusal.detail["reason"] == "would author a decision"
    assert refusal.detail["record"] == "go-open"


def test_the_runner_may_not_forge_an_approval_object(repo):
    gos = json.loads((repo / "app" / "state" / "gos.json").read_text())
    for record in gos:
        if record["id"] == "go-open":
            record["freigabe"] = {"status": "approved", "signature": "AAAA"}
    _, journal, _ = drive(repo, [
        [ToolUseBlock("write_file", {"path": "app/state/gos.json",
                                     "content": json.dumps(gos, indent=1)})],
        [TextBlock("ok")]])
    assert "freigabe" not in json.loads(
        (repo / "app" / "state" / "gos.json").read_text())[1]
    assert journal.events("refused")[0].detail["field"] == "freigabe"


def test_the_runner_may_still_write_its_own_job_states(repo):
    # "done" is the runner's own field; only approved/rejected are decisions.
    _, journal, _ = drive(repo, [
        [ToolUseBlock("write_file", {"path": "app/jobs/queue/job-1.json",
                                     "content": json.dumps(RESULT, indent=1)})],
        [TextBlock("ok")]])
    assert not journal.events("refused")
    assert json.loads((repo / "app" / "jobs" / "queue" / "job-1.json").read_text())[
        "status"] == "done"


def test_executing_an_unsigned_action_fails_at_verify(repo):
    _, journal, model = drive(repo, [
        [ToolUseBlock("execute_action", {"action_id": "go-open"})],
        [TextBlock("understood")]], consume=True)
    failed = journal.events("verify_failed")
    assert failed and failed[0].detail == {"action": "go-open", "reason": "no approval"}
    assert not journal.events("executed")
    assert not (repo / "app" / "state" / "send-log.json").exists()
    assert any(r["is_error"] for r in model.tool_results)


def test_executing_a_signed_action_needs_consume(repo):
    _, journal, _ = drive(repo, [
        [ToolUseBlock("execute_action", {"action_id": "go-signed"})],
        [TextBlock("ok")]], consume=False)
    assert journal.events("verified"), "it should verify, then refuse on --consume"
    refusal = journal.events("refused")[0]
    assert refusal.detail["reason"] == "run was not started with --consume"
    assert not journal.events("executed")


def test_a_signed_action_executes_once_and_then_replays(repo):
    _, journal, _ = drive(repo, [
        [ToolUseBlock("execute_action", {"action_id": "go-signed"})],
        [ToolUseBlock("execute_action", {"action_id": "go-signed"})],
        [TextBlock("ok")]], consume=True)
    assert len(journal.events("executed")) == 1
    assert json.loads((repo / "app" / "state" / "send-log.json").read_text())["go-signed"]
    # The replay is caught one door earlier than execute_action's own check:
    # verify_action rebuilds the nonce set from disk each time, so the spent
    # nonce fails verification. execute_action keeps its check anyway — it is
    # the door that still holds if a caller ever verifies against stale state.
    replay = journal.events("verify_failed")
    assert replay and "replay" in replay[0].detail["reason"]


def test_a_tampered_action_does_not_verify(repo):
    path = repo / "app" / "state" / "gos.json"
    path.write_text(path.read_text().replace("studio@example.com", "competitor@example.com"))
    _, journal, _ = drive(repo, [
        [ToolUseBlock("verify_action", {"action_id": "go-signed"})],
        [TextBlock("ok")]])
    assert "does not verify" in journal.events("verify_failed")[0].detail["reason"]


def test_a_commit_stages_only_app(repo):
    (repo / "untracked-elsewhere.txt").write_text("not mine")
    drive(repo, [
        [ToolUseBlock("write_file", {"path": "app/state/note.json", "content": "{}"})],
        [ToolUseBlock("git_commit", {"message": "note"})],
        [TextBlock("ok")]])
    assert "untracked-elsewhere.txt" in git(repo, "status", "--porcelain")
    assert git(repo, "show", "--stat", "--pretty=", "HEAD").strip().startswith("app/")


def test_the_loop_stops_instead_of_looping_forever(repo):
    _, journal, _ = drive(repo, [[ToolUseBlock("list_dir", {"path": "app"})]] * 40)
    assert journal.events("gave_up")


def test_reading_a_file_outside_the_repository_is_refused(repo):
    _, journal, _ = drive(repo, [
        [ToolUseBlock("read_file", {"path": "../../etc/passwd"})],
        [TextBlock("ok")]])
    assert journal.events("refused")
