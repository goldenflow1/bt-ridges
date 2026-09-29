"""One statement-derived scope policy shared by the edit tools and the guard: what may be edited, created, deleted."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from quarry.spec import TaskSpec

TEST_PATH = re.compile(
    r"(^|/)(tests?|spec|specs|__tests__|testdata|fixtures)(/|$)|(^|/)test_[^/]*\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$"
)
NEW_FILE_DIRS = re.compile(r"(^|/)(migrations?|migrate|alembic|versions|db|schema|sql)(/|$)")


class ScopePolicy:
    def __init__(self, spec: TaskSpec, target: Optional[Tuple[str, str]] = None):
        self.spec = spec
        self.scope = spec.scope
        self.target = target

    @property
    def files(self) -> List[str]:
        files = list(self.scope.files)
        for path in self.scope.new_files:
            if path not in files:
                files.append(path)
        if self.target and self.target[0] not in files:
            files.append(self.target[0])
        return files

    @property
    def symbols(self) -> List[str]:
        symbols = list(self.scope.symbols)
        if self.target and self.target[1] and self.target[1] not in symbols:
            symbols.append(self.target[1])
        return symbols

    @staticmethod
    def is_test(path: str) -> bool:
        return bool(TEST_PATH.search(path))

    def edit_refusal(self, path: str) -> str:
        """Why changing the existing file `path` is not allowed, or '' when it is."""
        if self.is_test(path) and not self.scope.allow_test_changes and path not in self.files:
            return "the statement does not allow changing tests"
        if self.scope.files and path not in self.files:
            return f"outside the allowed files {self.files}"
        return ""

    def create_refusal(self, path: str) -> str:
        """Why creating `path` is not allowed, or '' when it is."""
        if path in self.scope.new_files:
            return ""
        if self.is_test(path):
            return "" if self.scope.allow_test_changes else "the statement does not allow changing tests"
        if not self.scope.allow_new_files:
            return "the statement does not ask for new files"
        if self.scope.new_files:
            return f"the statement names the new files to create: {self.scope.new_files}"
        if self.scope.new_file_kind == "migration":
            return "" if NEW_FILE_DIRS.search(path) else "the statement asks for a migration; put it in the migrations directory"
        scope_dirs = {os.path.dirname(p) for p in self.files}
        if not self.files or os.path.dirname(path) in scope_dirs:
            return ""
        return "new files belong next to the files in scope"

    def delete_refusal(self, path: str) -> str:
        return "" if self.scope.allow_delete else "the statement does not ask to delete files"
