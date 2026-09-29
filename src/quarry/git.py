"""Git operations on the task repository: baseline, diff, change listing, restore, apply-checks, hand-off."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from typing import Dict, List, Optional, Set

from quarry.proc import ProcessRunner, ProcResult, run_full

# Disposable outputs of test runners, linters and builds. Everything else a run creates counts as state that
# validation may have depended on (templates, data files, configs, generated code of any extension).
ARTIFACT = re.compile(
    r"(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tox|\.nox|\.cache|node_modules|htmlcov|"
    r"\.hypothesis|\.next|\.turbo|\.gradle)(/|$)"
    r"|\.(pyc|pyo|log|tmp|swp)$|(^|/)(\.coverage[^/]*|coverage\.xml|junit[^/]*\.xml|test-results[^/]*|nohup\.out)$"
)


class ChangeSet:
    def __init__(self):
        self.modified: List[str] = []
        self.added: List[str] = []  # tracked as intent-to-add or staged new files
        self.deleted: List[str] = []
        self.untracked: List[str] = []
        self.mode_changed: Dict[str, str] = {}  # path -> baseline mode (e.g. "100644")

    def all_paths(self) -> List[str]:
        seen = self.modified + self.added + self.deleted + self.untracked + list(self.mode_changed)
        return sorted(set(seen))


class GitRepo:
    """All comparisons use the baseline commit captured at start, never the moving symbolic HEAD."""

    def __init__(self, root: str, runner: Optional[ProcessRunner] = None):
        self.root = os.path.abspath(root)
        self.runner = runner or ProcessRunner(self.root)
        self.head = ""
        self.initial_untracked: Set[str] = set()
        self.initial_dirty: Set[str] = set()

    @property
    def base(self) -> str:
        return self.head or "HEAD"

    def git(self, *args: str, timeout: float = 60.0, env: Optional[dict] = None, stdin: Optional[str] = None) -> ProcResult:
        return run_full(["git", "-c", "core.quotepath=off", *args], self.root, timeout=timeout, env=env, stdin=stdin)

    def ensure_baseline(self) -> str:
        """Make sure a commit exists (same idea as the platform's baseline), pin it, and snapshot the start state."""
        if not self.git("rev-parse", "HEAD").ok:
            self.git("init", "-q")
            self.git("config", "user.email", "agent@localhost")
            self.git("config", "user.name", "agent")
            self.git("add", "-A")
            self.git("commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "baseline", timeout=300)
        self.head = self.git("rev-parse", "HEAD").output.strip()
        start = self.changed()
        self.initial_untracked = set(start.untracked)
        self.initial_dirty = set(start.modified + start.deleted + start.added + list(start.mode_changed))
        return self.head

    def diff(self) -> str:
        result = self.git("diff", "--binary", self.base, timeout=120)
        return result.output if result.ok else ""

    def fingerprint(self) -> str:
        """Identity of the state a check ran on: the diff plus every untracked file that is not a disposable
        artifact. A helper, template or data file created by a check changes it, though it is not in the diff."""
        digest = hashlib.sha256(self.diff().encode())
        for path in sorted(self.changed().untracked):
            if not ARTIFACT.search(path):
                digest.update(b"\0" + path.encode() + b"\0")
                try:
                    with open(os.path.join(self.root, path), "rb") as handle:
                        digest.update(handle.read())
                except OSError:
                    digest.update(b"<unreadable>")
        return digest.hexdigest()

    def changed(self) -> ChangeSet:
        changes = ChangeSet()
        content_changed = set()
        for entry in self.git("diff", "--numstat", "-z", "--no-renames", self.base).output.split("\0"):
            bits = entry.split("\t")
            if len(bits) == 3 and bits[:2] != ["0", "0"]:
                content_changed.add(bits[2])
        parts = self.git("diff", "--raw", "-z", "--no-renames", self.base).output.split("\0")
        for meta, path in zip(parts[0::2], parts[1::2]):
            if not meta.startswith(":"):
                continue
            old_mode, new_mode, _old_id, _new_id, status = meta[1:].split()[:5]
            if status.startswith("A"):
                changes.added.append(path)
            elif status.startswith("D"):
                changes.deleted.append(path)
            else:
                if old_mode != new_mode:
                    changes.mode_changed[path] = old_mode
                if path in content_changed:
                    changes.modified.append(path)
        untracked = self.git("ls-files", "--others", "--exclude-standard", "-z").output
        changes.untracked = [p for p in untracked.split("\0") if p]
        return changes

    def head_text(self, path: str) -> Optional[str]:
        result = self.git("show", f"{self.base}:{path}")
        return result.output if result.ok else None

    def head_mode(self, path: str) -> Optional[str]:
        out = self.git("ls-tree", self.base, "--", path).output.strip()
        return out.split()[0] if out else None

    def restore(self, path: str) -> None:
        """Bring one path back to exactly its baseline state (content and mode), or delete it if new."""
        if self.head_mode(path) is None:
            self.git("rm", "-q", "--cached", "--ignore-unmatch", "--", path)
            full = os.path.join(self.root, path)
            if os.path.isfile(full) or os.path.islink(full):
                os.unlink(full)
            return
        self.git("checkout", self.base, "--", path)
        self.restore_mode(path)

    def restore_mode(self, path: str) -> None:
        mode = self.head_mode(path)
        full = os.path.join(self.root, path)
        if mode and os.path.isfile(full) and not os.path.islink(full):
            wanted = 0o755 if mode == "100755" else 0o644
            current = stat.S_IMODE(os.lstat(full).st_mode)
            if current & 0o111 != wanted & 0o111:
                os.chmod(full, (current & ~0o111) | (wanted & 0o111))

    def intent_to_add(self, path: str) -> None:
        self.git("add", "-N", "--", path)

    def undo_run_changes(self) -> List[str]:
        """Return the tree, index and HEAD to the start state. Paths that were already dirty at start are left alone."""
        if self.head and self.git("rev-parse", "HEAD").output.strip() != self.head:
            self.git("reset", "-q", "--soft", self.head)
        changes = self.changed()
        undone = []
        for path in changes.all_paths():
            if path in self.initial_dirty or path in self.initial_untracked:
                continue
            self.restore(path)
            undone.append(path)
        return undone

    def apply_check(self, patch: str) -> ProcResult:
        """Check `patch` applies to the pristine baseline, using a throw-away index (working tree untouched)."""
        if not patch.strip():
            return ProcResult(1, "empty patch")
        with tempfile.TemporaryDirectory(prefix="quarry-idx-") as tmp:
            index = os.path.join(tmp, "index")
            patch_file = os.path.join(tmp, "p.diff")
            with open(patch_file, "w", encoding="utf-8", newline="") as handle:
                handle.write(patch)
            env = {"GIT_INDEX_FILE": index}
            read = self.git("read-tree", self.base, env=env)
            if not read.ok:
                return read
            return self.git("apply", "--check", "--cached", patch_file, env=env)

    def apply_check_worktree(self, patch: str) -> ProcResult:
        """The same check the platform runs after the agent returns: `git apply --check` on the working tree."""
        if not patch.strip():
            return ProcResult(1, "empty patch")
        with tempfile.TemporaryDirectory(prefix="quarry-patch-") as tmp:
            patch_file = os.path.join(tmp, "p.diff")
            with open(patch_file, "w", encoding="utf-8", newline="") as handle:
                handle.write(patch)
            return self.git("apply", "--check", patch_file)

