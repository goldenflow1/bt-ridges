import os
import subprocess

import pytest

from quarry.git import GitRepo


def write(root, rel, text, mode=None, newline=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path) or root, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as handle:
        handle.write(text)
    if mode is not None:
        os.chmod(path, mode)
    return path


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", newline="") as handle:
        return handle.read()


@pytest.fixture
def make_repo(tmp_path):
    """Create a git repo with a baseline commit, like the platform does before the agent runs."""

    def factory(files, modes=None):
        root = str(tmp_path / "repo")
        os.makedirs(root, exist_ok=True)
        for rel, text in files.items():
            write(root, rel, text, (modes or {}).get(rel, 0o644))
        repo = GitRepo(root)
        repo.ensure_baseline()
        return repo

    return factory


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout
