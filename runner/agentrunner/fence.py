"""The path fence.

One rule, enforced in one place: a run may write under ``app/`` and nowhere
else. It is a rule about paths, not about intentions, so it is checked after
resolving symlinks and ``..`` — the two ways a path that looks contained
stops being contained.
"""

from __future__ import annotations

from pathlib import Path

WRITABLE_ROOT = "app"


class FenceError(Exception):
    """A refusal. The message names the path and the reason, because refusals
    that cannot be read are refusals that get switched off."""


class Fence:
    def __init__(self, repo: Path, writable_root: str = WRITABLE_ROOT) -> None:
        self.repo = repo.resolve()
        if not self.repo.is_dir():
            raise FenceError(f"repository path is not a directory: {self.repo}")
        self.writable = (self.repo / writable_root).resolve()

    def resolve_for_read(self, relative: str) -> Path:
        """Anywhere inside the repository may be read. Outside it, nothing."""
        return self._inside(relative, self.repo, "read")

    def resolve_for_write(self, relative: str) -> Path:
        """Only ``app/**``. This is the whole safety story of the write tool."""
        return self._inside(relative, self.writable, "write")

    def _inside(self, relative: str, root: Path, what: str) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute():
            raise FenceError(f"refused to {what} {relative!r}: absolute paths are not accepted")

        target = (self.repo / candidate)
        # Resolve the deepest existing ancestor: a file that does not exist yet
        # still must not sit behind a symlink that leaves the fence.
        probe = target
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        resolved_base = probe.resolve()
        remainder = target.relative_to(probe) if target != probe else Path()
        resolved = (resolved_base / remainder)

        if not self._is_within(resolved, root):
            raise FenceError(
                f"refused to {what} {relative!r}: resolves to {resolved}, "
                f"which is outside {root}")
        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        return path == root or root in path.parents
