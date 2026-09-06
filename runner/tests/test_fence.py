"""The fence. Each test is one way a path can pretend to be inside."""

import pytest
from agentrunner.fence import Fence, FenceError


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "app" / "state").mkdir(parents=True)
    (tmp_path / "app" / "state" / "gos.json").write_text("[]")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    (tmp_path / "secrets.env").write_text("TOKEN=1")
    return tmp_path


def test_a_normal_path_under_app_is_writable(repo):
    assert Fence(repo).resolve_for_write("app/state/gos.json").name == "gos.json"


def test_a_file_that_does_not_exist_yet_is_writable(repo):
    assert Fence(repo).resolve_for_write("app/jobs/done/new.json").name == "new.json"


def test_a_sibling_of_app_is_not_writable(repo):
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_write("secrets.env")


def test_dot_dot_does_not_climb_out(repo):
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_write("app/../.git/config")


def test_dot_dot_does_not_leave_the_repository(repo):
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_write("app/../../etc/passwd")


def test_an_absolute_path_is_refused_before_anything_else(repo):
    with pytest.raises(FenceError, match="absolute"):
        Fence(repo).resolve_for_write("/etc/passwd")


def test_a_symlink_pointing_out_is_refused(repo):
    (repo / "app" / "escape").symlink_to(repo / ".git")
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_write("app/escape/config")


def test_a_symlink_whose_parent_points_out_is_refused_even_for_a_new_file(repo):
    # The file does not exist, so a naive check would look at the string only.
    (repo / "app" / "escape").symlink_to(repo.parent)
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_write("app/escape/anywhere.json")


def test_reading_is_allowed_anywhere_in_the_repository(repo):
    assert Fence(repo).resolve_for_read(".git/config").name == "config"


def test_reading_outside_the_repository_is_refused(repo):
    with pytest.raises(FenceError, match="outside"):
        Fence(repo).resolve_for_read("../../etc/passwd")


def test_a_repository_that_is_not_a_directory_is_refused_at_construction(tmp_path):
    file = tmp_path / "not-a-repo"
    file.write_text("")
    with pytest.raises(FenceError, match="not a directory"):
        Fence(file)
