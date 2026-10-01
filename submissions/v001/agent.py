"""Quarry: an agent that changes how an application fetches data from PostgreSQL or ClickHouse.

Single-file build of the quarry package (see src/quarry/ in the project for the module sources).
Entry point: agent_main({"problem_statement": ...}) -> unified diff.
"""

from __future__ import annotations

import sys
import types

# Loaders may execute this file without registering it in sys.modules; dataclasses (Python < 3.12)
# looks the defining module up there, so make sure an entry exists.
sys.modules.setdefault(__name__, types.ModuleType(__name__))

EMBEDDED_ASSETS = {
    "prompts/checks_failed.md": """\
Your change is not ready. The following problems were found after your last edit. Fix them, re-verify, and call `finish` again.
""",
    "prompts/driver.md": """\
You are a senior engineer who specialises in how applications read data from PostgreSQL and ClickHouse. You are working in a real application repository with a live database. Your job is to change the production code path so the application returns the right data, in the right shape, efficiently.

How to work:
1. Understand the requirement. The task checklist below is the contract; every numbered requirement must hold for every state of the data it describes, not only the rows present now.
2. Locate the code the application actually runs for this data: the query, ORM expression, query builder, manager, filter or migration. Read the caller to see what it does with the result (columns, grain, ordering, types).
3. Read the schema that matters: tables, columns, nullability, keys, indexes, and for ClickHouse the table engine and ORDER BY key.
4. Before editing, reproduce the current behaviour on small crafted data (SQL in a rolled-back transaction, or a scratch script outside the repository) and write down what the correct output must be, derived from the requirement. Think about duplicates, joins that multiply rows, NULLs, empty groups, ties, time zones and boundaries.
5. Make the smallest change that satisfies every requirement. Keep the change inside the allowed files and symbols. Keep signatures and imports as they are when asked; use only names the file already imports.
6. Verify: run the checks the task lists, re-run your scenario and confirm the output now matches the expected result. For performance work, confirm results are identical and that the number of queries or the database work no longer grows with the data.
7. Call `finish` with a short summary.

Tool rules:
- Paths are relative to the repository root. Read files in ranges; search before reading whole directories.
- `edit` needs `old` to match exactly once. Re-read the file after a failed edit.
- Never create helper files inside the repository; use `scratch` for throw-away scripts and run them with `shell`.
- Database changes you make while exploring are temporary. A schema or index change the task needs must ship as code (for example a migration), never only in the live database.
- Do not reformat code you did not need to change. Do not edit tests unless the task asks for it.
- Prefer several independent tool calls in one reply when you can.
""",
    "prompts/kind_authoring.md": """\
This task asks you to write a data path that does not exist yet (or returns placeholder values). Before writing code, derive the expected output for a few small scenarios directly from the requirements, including empty and tie cases; then implement and compare.
""",
    "prompts/kind_optimization.md": """\
This task asks for less database work with identical results. First capture the current results and the current number of queries (or plan / rows read) on realistic volume, then change the code, then show the results are identical and that the work no longer grows with the data.
""",
    "prompts/kind_repair.md": """\
The code returns wrong data. Reproduce the defect on crafted data first, write down the correct output from the requirements, then fix it at its source in the production path and show old-wrong / new-right on the same data.
""",
    "packs/clickhouse.md": """\
ClickHouse notes:
- ReplacingMergeTree / CollapsingMergeTree deduplicate only when parts merge, which may never happen before a query. Deduplicate in the query: FINAL on the table, or argMax(value, version) grouped by the key at the right grain, before any further aggregation.
- JOINs fill missing right-side values with type defaults (0, '', 1970-01-01), not NULL, unless join_use_nulls = 1. Test for "no match" accordingly.
- uniq() is approximate; use uniqExact() when an exact count is required.
- Top N per group: LIMIT n BY key after ORDER BY with a deterministic tie-breaker.
- Time: toStartOfDay/toStartOfInterval take a time zone argument; DateTime columns may carry their own zone. Generate missing buckets with WITH FILL or numbers()/arrayJoin.
- Performance: filters on a prefix of the table's ORDER BY key use the primary index; PREWHERE for selective columns; data-skipping indexes need a migration. Measure read_rows/read_bytes in system.query_log or with EXPLAIN indexes = 1.
- Nullable columns change aggregate semantics (NULLs are skipped); avoid mixing with default values.
- Build test scenarios without writing tables: SELECT ... FROM values('k UInt32, v String', (1, 'a'), (2, 'b')) or numbers(N).
""",
    "packs/core.md": """\
Data semantics checklist (all engines):
- Joins change grain. Joining a one-to-many relation before aggregating multiplies rows; aggregate each relation at its own grain first (subquery/CTE), or use EXISTS for filters. DISTINCT inside SUM/AVG is not a fix: equal values from different rows collapse.
- COUNT(*) counts rows, COUNT(col) skips NULLs, COUNT(DISTINCT col) collapses duplicates. Pick the one the requirement means.
- A LEFT JOIN followed by a WHERE on the right table becomes an inner join; move the condition into the ON clause.
- NOT IN with a subquery that can return NULL returns no rows; use NOT EXISTS.
- Empty groups: aggregates over no rows return NULL; wrap with COALESCE(..., 0) when the caller expects a number, and keep the group row with an outer join or correlated subquery.
- Ordering: "latest", "first", "top N" and pagination need a total order. Add a unique tie-breaker (usually the primary key) to ORDER BY and to keyset predicates (row comparison `(a, id) > (x, y)`).
- Integer division truncates; cast to numeric/decimal before dividing, then round.
- Time: use half-open ranges [start, end); be explicit about the time zone of day/week buckets; beware end-of-day inclusive bounds.
- Hierarchies: "descendants at any depth" means the whole subtree, not one level; count distinct leaf entities once.
- Keep query objects lazy and composable when the code returns a queryset/builder: callers may filter, order, slice or select values afterwards.
- N+1: a query per row inside a loop grows with data. Replace with one set-based query, a join, or batched loading (IN (...) / prefetch).
- Verify on data that exercises the edge cases above, not only the rows that happen to exist.
""",
    "packs/django.md": """\
Django ORM notes:
- Correlated aggregates: Subquery(Model.objects.filter(fk=OuterRef("pk")).values("fk").annotate(c=Count("pk")).values("c")) with Coalesce(..., 0) avoids join fan-out; output_field must match (IntegerField for counts).
- annotate() over several multi-valued relations multiplies rows; use separate subqueries or Count(..., distinct=True) only when distinctness is the requirement.
- values() before annotate() groups by those values; order_by() fields also join the GROUP BY.
- Never hard-code compiler table aliases in RawSQL/extra(); outer references in RawSQL break when the queryset is filtered or joined.
- Integer arithmetic in expressions stays integer; use Cast(..., FloatField()/DecimalField()) or ExpressionWrapper with an explicit output_field before dividing, then Round.
- N+1: select_related for forward FK/one-to-one, prefetch_related for reverse/many-to-many; Prefetch(queryset=...) to filter.
- Tests: `python manage.py test <label> --keepdb --noinput` reuses the test database. Query counts: django.test.utils.CaptureQueriesContext(connection) or connection.execute_wrapper.
- Migrations: indexes via migrations.AddIndex/models.Index(fields=..., condition=Q(...), name=...); AddIndexConcurrently needs atomic = False.
""",
    "packs/go.md": """\
Go data-access notes:
- database/sql: scan nullable columns into sql.NullInt64/NullString/NullTime (or pointers); always check rows.Err() after iterating and close rows.
- sqlx: Select/Get map by `db` tags; In() expands slices and must be followed by Rebind() for PostgreSQL placeholders.
- sqlc: queries live in .sql files and generated Go code must stay consistent. If the generator is not available, update the generated query string and scan code by hand exactly as the generator would.
- GORM: Preload for associations (one query per association), Joins for filtering; Count() with joins counts joined rows.
- pgx: batch queries with pgx.Batch; use placeholders $1..$n, never string concatenation.
- Verify with `go build ./...`, `go vet ./<pkg>/...` and `go test ./<pkg>/... -run <Name>`.
""",
    "packs/postgresql.md": """\
PostgreSQL notes:
- DISTINCT ON (a) requires ORDER BY to start with a; the rest of ORDER BY picks the row.
- NULLs sort last in ASC and first in DESC by default; use NULLS FIRST/LAST explicitly when it matters.
- Window functions: the default frame with ORDER BY is RANGE UNBOUNDED PRECEDING .. CURRENT ROW, which includes peers (ties); use ROWS for a running total per row. last_value() needs an explicit frame.
- Index use: composite index column order must match equality columns first, then range/order columns. A partial index is used only when the query predicate implies the index predicate. Expression indexes must match the expression exactly (e.g. lower(email)).
- Check plans with EXPLAIN (ANALYZE, BUFFERS) on realistic volume after ANALYZE; tiny tables always get sequential scans. EXPLAIN ANALYZE executes the statement, so run it in a transaction you roll back.
- CREATE INDEX CONCURRENTLY cannot run inside a transaction block (a framework migration must be marked non-atomic).
- numeric / integer: int / int is integer division. ROUND(numeric, 2) needs numeric, not double precision.
""",
    "packs/python.md": """\
Python data-access notes:
- Run throw-away checks as scripts in the scratch directory that import the application (put the repository on sys.path and load its settings/config). Never add files to the repository for this.
- Count queries at the driver level (a cursor wrapper or the ORM's query-capture hook) rather than relying on database-side logging.
""",
    "packs/sqlalchemy.md": """\
SQLAlchemy 2.x notes:
- select(...).join(...) multiplies rows for one-to-many; aggregate in a subquery (.subquery()) or use scalar_subquery() correlated with the outer entity.
- func.count() counts rows; func.count(col) skips NULLs; func.coalesce(..., 0) for empty groups; aggregate FILTER via func.count().filter(cond).
- Eager loading: selectinload() for collections (one extra query per relationship), joinedload() for many-to-one; raiseload('*') helps find lazy loads.
- Query counting: event.listen(engine, "before_cursor_execute", ...).
- Alembic: op.create_index(name, table, cols, postgresql_where=text(...)) for partial indexes.
""",
    "packs/typescript.md": """\
TypeScript data-access notes:
- Prisma: include/select for relations, groupBy/_count for aggregates; $queryRaw uses tagged templates (parameters are bound, not interpolated) and returns bigint for COUNT in PostgreSQL. Avoid schema changes unless required; the client may not regenerate offline.
- TypeORM: leftJoinAndSelect multiplies rows; getCount/getManyAndCount on joined queries can count joined rows; getRawMany returns raw column aliases.
- Knex/Kysely/Drizzle: build window functions and subqueries with raw fragments carefully; keep parameters bound.
- @clickhouse/client: query({ query, format: 'JSONEachRow', query_params }) with {name:Type} placeholders.
- Verify with `npx tsc --noEmit -p .` (using the local node_modules; do not download packages) and the project's test script.
""",
}


# ======================================================================
# module: quarry.assets
# ======================================================================

"""Prompt and knowledge-pack text. The single-file build embeds them in EMBEDDED_ASSETS; development reads the files."""


import os
from typing import List

ASSET_DIR = os.path.dirname(os.path.abspath(globals().get("__file__") or "."))


def asset(rel: str) -> str:
    embedded = globals().get("EMBEDDED_ASSETS")
    if isinstance(embedded, dict) and rel in embedded:
        return embedded[rel]
    try:
        with open(os.path.join(ASSET_DIR, rel), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def pack_text(names: List[str]) -> str:
    parts = [asset(f"packs/{name}.md").strip() for name in names]
    return "\n\n".join(part for part in parts if part)


# ======================================================================
# module: quarry.clock
# ======================================================================

"""Wall-clock budget: overall deadline, reserve for wrap-up, and per-phase slices."""


import os
import time
from typing import Callable, Optional

DEFAULT_TIMEOUT_SEC = 1500.0
MIN_RESERVE_SEC = 60.0
RESERVE_SHARE = 0.05


def read_timeout_env(environ: Optional[dict] = None) -> float:
    """Return AGENT_TIMEOUT in seconds, or the default when it is missing or invalid."""
    env = os.environ if environ is None else environ
    raw = str(env.get("AGENT_TIMEOUT", "")).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SEC
    return value if value > 0 else DEFAULT_TIMEOUT_SEC


class Clock:
    """Tracks the run deadline. `now` is injectable so tests control time."""

    def __init__(self, total_sec: float, now: Callable[[], float] = time.monotonic):
        self._now = now
        self.start = now()
        self.total = float(total_sec)
        self.reserve = max(MIN_RESERVE_SEC, RESERVE_SHARE * self.total)
        self.deadline = self.start + self.total - self.reserve

    @classmethod
    def from_env(cls, environ: Optional[dict] = None, now: Callable[[], float] = time.monotonic) -> Clock:
        return cls(read_timeout_env(environ), now)

    def now(self) -> float:
        return self._now()

    def elapsed(self) -> float:
        return self._now() - self.start

    def remaining(self) -> float:
        """Seconds left before wrap-up must start (never negative)."""
        return max(0.0, self.deadline - self._now())

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def slice(self, share: float) -> PhaseTimer:
        """A timer for one phase: its share of the total, never past the deadline."""
        budget = min(share * self.total, self.remaining())
        return PhaseTimer(self, self._now() + budget)

    def command_timeout(self, cap: float = 300.0) -> float:
        """Timeout for one command: min(cap, 25% of what is left), at least 5 s."""
        return max(5.0, min(cap, 0.25 * self.remaining()))


class PhaseTimer:
    def __init__(self, clock: Clock, end: float):
        self.clock = clock
        self.end = min(end, clock.deadline)

    def remaining(self) -> float:
        return max(0.0, self.end - self.clock.now())

    def expired(self) -> bool:
        return self.remaining() <= 0.0


# ======================================================================
# module: quarry.proc
# ======================================================================

"""Subprocess execution with timeouts, process groups and bounded output buffering."""


import os
import re
import signal
import subprocess
import threading
from typing import List, Optional, Sequence, Set, Union

ERROR_LINE = re.compile(r"(error|fail|exception|traceback|assert|panic|fatal)", re.IGNORECASE)
HEAD_BYTES = 256 * 1024
TAIL_BYTES = 768 * 1024


class ProcResult:
    def __init__(self, code: int, output: str, timed_out: bool = False):
        self.code = code
        self.output = output
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out


class BoundedBuffer:
    """Keeps the first HEAD_BYTES and the last TAIL_BYTES of a stream; memory stays bounded."""

    def __init__(self, head: int = HEAD_BYTES, tail: int = TAIL_BYTES):
        self.head_limit, self.tail_limit = head, tail
        self.head = bytearray()
        self.tail = bytearray()
        self.dropped = 0

    def feed(self, chunk: bytes) -> None:
        room = self.head_limit - len(self.head)
        if room > 0:
            self.head += chunk[:room]
            chunk = chunk[room:]
        if chunk:
            self.tail += chunk
            excess = len(self.tail) - self.tail_limit
            if excess > 0:
                del self.tail[:excess]
                self.dropped += excess

    def text(self) -> str:
        middle = f"\n[... {self.dropped} bytes of output dropped ...]\n".encode() if self.dropped else b""
        return (bytes(self.head) + middle + bytes(self.tail)).decode("utf-8", "replace")


class ProcessRunner:
    """Runs commands in their own process group so they can always be killed."""

    def __init__(self, cwd: str):
        self.cwd = cwd
        self._live: Set[int] = set()

    def run(
        self,
        cmd: Union[str, Sequence[str]],
        timeout: float = 120.0,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        stdin: Optional[str] = None,
    ) -> ProcResult:
        shell = isinstance(cmd, str)
        merged_env = dict(os.environ)
        merged_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        if env:
            merged_env.update(env)
        proc = subprocess.Popen(
            cmd,
            shell=shell,
            cwd=cwd or self.cwd,
            env=merged_env,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            executable="/bin/bash" if shell else None,
        )
        self._live.add(proc.pid)
        buffer = BoundedBuffer()

        def pump() -> None:
            while True:
                chunk = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(65536)
                if not chunk:
                    break
                buffer.feed(chunk)

        def feed_stdin() -> None:
            try:
                proc.stdin.write(stdin.encode())
                proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        if stdin is not None:
            threading.Thread(target=feed_stdin, daemon=True).start()
        timed_out = False
        try:
            proc.wait(timeout=max(0.1, timeout))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            _kill_group(proc.pid)
            self._live.discard(proc.pid)
        reader.join(timeout=5)
        try:
            proc.stdout.close()
        except OSError:
            pass
        if timed_out:
            proc.wait(timeout=5)
            return ProcResult(124, buffer.text() + f"\n[timed out after {timeout:.0f}s]", True)
        return ProcResult(proc.returncode, buffer.text())

    def kill_all(self) -> None:
        for pid in list(self._live):
            _kill_group(pid)
        self._live.clear()


def run_full(args: Sequence[str], cwd: str, timeout: float = 120.0, env: Optional[dict] = None,
             stdin: Optional[str] = None) -> ProcResult:
    """Unbounded capture for trusted internal commands whose output must stay exact (git diff, git show)."""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        done = subprocess.run(
            list(args), cwd=cwd, env=merged_env, input=stdin.encode() if stdin is not None else None,
            capture_output=True, timeout=timeout, start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        return ProcResult(124, f"[timed out after {timeout:.0f}s]", True)
    out = done.stdout.decode("utf-8", "replace")
    if done.returncode:
        out += done.stderr.decode("utf-8", "replace")
    return ProcResult(done.returncode, out)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def cap_output(text: str, limit: int = 6000) -> str:
    """Keep the head, the tail and error-looking lines from the middle."""
    if len(text) <= limit:
        return text
    head_len = limit // 3
    tail_len = limit // 3
    head, middle, tail = text[:head_len], text[head_len:-tail_len], text[-tail_len:]
    picked: List[str] = []
    budget = limit - head_len - tail_len - 80
    for line in middle.splitlines():
        if ERROR_LINE.search(line) and budget > len(line):
            picked.append(line)
            budget -= len(line) + 1
    omitted = len(middle) - sum(len(line) + 1 for line in picked)
    return head + f"\n[... {omitted} chars omitted ...]\n" + "\n".join(picked) + "\n" + tail


# ======================================================================
# module: quarry.git
# ======================================================================

"""Git operations on the task repository: baseline, diff, change listing, restore, apply-checks, hand-off."""


import hashlib
import os
import re
import stat
import tempfile
from typing import Dict, List, Optional, Set


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


# ======================================================================
# module: quarry.pysource
# ======================================================================

"""Python source surgery: locate a symbol, splice it byte-exactly, and check its header, imports and constructs."""


import ast
import builtins
from typing import List, Optional, Set, Tuple

FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

# Rules checked on the whole candidate symbol ("absolute"): the statement forbids the construct outright.
ABSOLUTE_RULE_NODES = {
    "no_loops": ("For", "AsyncFor", "While"),
    "no_comprehensions": ("ListComp", "SetComp", "DictComp", "GeneratorExp"),
    "no_lambdas": ("Lambda",),
    "no_exception_handling": ("Try", "TryStar", "Raise"),
    "no_context_managers": ("With", "AsyncWith"),
}
DYNAMIC_NAMES = {"eval", "exec", "compile", "getattr", "setattr", "delattr", "__import__", "globals", "locals", "vars", "open"}
# Rules checked as "introduced by the patch": the statement says not to *add* them.
WRITE_ATTRS = {
    "save", "delete", "update", "create", "bulk_create", "bulk_update", "get_or_create", "update_or_create",
    "executemany", "insert",
}
RAW_SQL_ATTRS = {"raw", "execute", "cursor", "extra", "executescript"}
RAW_SQL_NAMES = {"RawSQL"}
MATERIALIZE_NAMES = {"list", "tuple", "set", "sorted", "len", "sum", "dict"}
SOFT_BYTES = 4500
SOFT_NODES = 300


def find_symbol(tree: ast.Module, dotted: str) -> Optional[ast.AST]:
    """Find `Class.method`, `func`, or `Outer.Inner.method` among top-level definitions."""
    parts = [p for p in dotted.split(".") if p]
    scope: List[ast.stmt] = list(tree.body)
    node: Optional[ast.AST] = None
    for part in parts:
        matches = [n for n in scope if isinstance(n, DEF_TYPES) and n.name == part]
        if len(matches) != 1:
            return None
        node = matches[0]
        scope = list(node.body)
    return node


def find_symbol_anywhere(tree: ast.Module, name: str) -> List[str]:
    """All dotted paths whose last part is `name` (used when the statement names only a method)."""
    found: List[str] = []

    def visit(nodes, prefix):
        for node in nodes:
            if isinstance(node, DEF_TYPES):
                path = prefix + [node.name]
                if node.name == name:
                    found.append(".".join(path))
                if isinstance(node, ast.ClassDef):
                    visit(node.body, path)

    visit(tree.body, [])
    return found


def span(node: ast.AST) -> Tuple[int, int]:
    """1-based inclusive line span including decorators."""
    start = node.lineno
    for deco in getattr(node, "decorator_list", []) or []:
        start = min(start, deco.lineno)
    return start, node.end_lineno


def splice(original: str, candidate: str, dotted: str) -> Optional[str]:
    """Original text everywhere except the symbol's span, which comes from the candidate."""
    try:
        orig_node = find_symbol(ast.parse(original), dotted)
        cand_node = find_symbol(ast.parse(candidate), dotted)
    except SyntaxError:
        return None
    if orig_node is None or cand_node is None:
        return None
    o_start, o_end = span(orig_node)
    c_start, c_end = span(cand_node)
    o_lines = original.splitlines(keepends=True)
    c_lines = candidate.splitlines(keepends=True)
    body = c_lines[c_start - 1:c_end]
    if body and o_end <= len(o_lines) and o_lines[o_end - 1:o_end]:
        # keep the original line ending on the symbol's last line
        orig_last = o_lines[o_end - 1]
        ending = orig_last[len(orig_last.rstrip("\r\n")):]
        body[-1] = body[-1].rstrip("\r\n") + ending
    return "".join(o_lines[:o_start - 1] + body + o_lines[o_end:])


def outside_identical(original: str, candidate: str, dotted: str) -> Tuple[bool, str]:
    try:
        orig_node = find_symbol(ast.parse(original), dotted)
        cand_node = find_symbol(ast.parse(candidate), dotted)
    except SyntaxError as exc:
        return False, f"syntax error: {exc}"
    if orig_node is None or cand_node is None:
        return False, f"symbol {dotted} not found exactly once"
    o_start, o_end = span(orig_node)
    c_start, c_end = span(cand_node)
    o_lines = original.splitlines(keepends=True)
    c_lines = candidate.splitlines(keepends=True)
    if o_lines[:o_start - 1] != c_lines[:c_start - 1]:
        return False, "text before the symbol changed"
    if o_lines[o_end:] != c_lines[c_end:]:
        return False, "text after the symbol changed"
    return True, "only the symbol changed"


def _dump(value) -> object:
    if isinstance(value, ast.AST):
        return ast.dump(value, include_attributes=False)
    if isinstance(value, list):
        return [_dump(v) for v in value]
    return value


def header_equal(orig: ast.AST, cand: ast.AST) -> Tuple[bool, str]:
    if type(orig) is not type(cand):
        return False, "definition kind changed"
    for name in ("name", "args", "decorator_list", "returns", "type_params"):
        if _dump(getattr(orig, name, None)) != _dump(getattr(cand, name, None)):
            return False, f"header field changed: {name}"
    return True, "header unchanged"


def module_imports(tree: ast.Module) -> List[str]:
    return [ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]


def module_bindings(tree: ast.Module) -> Set[str]:
    names: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, DEF_TYPES):
            names.add(node.name)
        else:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for alias in sub.names:
                        names.add((alias.asname or alias.name).split(".")[0])
    return names


def unbound_names(func: ast.AST, tree: ast.Module) -> List[str]:
    """Names the symbol reads that are bound nowhere: not local, not module-level, not builtin."""
    local: Set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.arg):
            local.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            local.add(node.id)
        elif isinstance(node, DEF_TYPES) and node is not func:
            local.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            local.add(node.name)
    known = local | module_bindings(tree) | set(dir(builtins)) | {"__class__"}
    missing = sorted({
        n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in known
    })
    return missing


def _count(node: ast.AST, predicate) -> int:
    return sum(1 for sub in ast.walk(node) if predicate(sub))


def _is_attr_call(names: Set[str]):
    return lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in names


def _is_name(names: Set[str]):
    return lambda n: isinstance(n, ast.Name) and n.id in names


def rule_violations(cand: ast.AST, orig: Optional[ast.AST], rules: List[str]) -> Tuple[List[str], List[str]]:
    """Return (hard violations, soft warnings) for the statement-derived rules."""
    hard: List[str] = []
    soft: List[str] = []
    body = ast.Module(body=list(getattr(cand, "body", [])), type_ignores=[])
    for rule in rules:
        node_names = ABSOLUTE_RULE_NODES.get(rule)
        if node_names:
            hits = sorted({type(n).__name__ for n in ast.walk(body) if type(n).__name__ in node_names})
            if hits:
                hard.append(f"{rule}: found {', '.join(hits)}")
        elif rule == "no_dynamic_code":
            hits = sorted({
                n.id for n in ast.walk(body) if isinstance(n, ast.Name) and (n.id in DYNAMIC_NAMES or "__" in n.id)
            } | {n.attr for n in ast.walk(body) if isinstance(n, ast.Attribute) and "__" in n.attr})
            if hits:
                hard.append(f"{rule}: found {', '.join(hits)}")
        elif rule in ("no_db_writes", "no_raw_sql"):
            if rule == "no_db_writes":
                pred = _is_attr_call(WRITE_ATTRS)
            else:
                attr_pred, name_pred = _is_attr_call(RAW_SQL_ATTRS), _is_name(RAW_SQL_NAMES)

                def pred(n, a=attr_pred, b=name_pred):
                    return a(n) or b(n)
            before = _count(orig, pred) if orig is not None else 0
            after = _count(cand, pred)
            if after > before:
                hard.append(f"{rule}: patch adds {after - before} such call(s)")
        elif rule == "no_python_materialization":
            calls = sorted({
                n.func.id for n in ast.walk(body)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MATERIALIZE_NAMES
            })
            if calls:
                soft.append(f"{rule}: calls {', '.join(calls)}() may load rows into Python")
    source_len = len(ast.unparse(cand)) if hasattr(ast, "unparse") else 0
    nodes = _count(cand, lambda n: True)
    if source_len > SOFT_BYTES or nodes > SOFT_NODES:
        soft.append(f"symbol is large ({source_len} chars, {nodes} AST nodes); prefer the smallest correct expression")
    return hard, soft


def parse_or_none(text: Optional[str]) -> Optional[ast.Module]:
    if text is None:
        return None
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _rule_predicates(rule: str):
    """Node predicate for a rule, used when comparing whole modules (counts before vs after)."""
    names = ABSOLUTE_RULE_NODES.get(rule)
    if names:
        return lambda n: type(n).__name__ in names
    if rule == "no_dynamic_code":
        return lambda n: (isinstance(n, ast.Name) and (n.id in DYNAMIC_NAMES or ("__" in n.id and n.id != "__name__"))) or (
            isinstance(n, ast.Attribute) and "__" in n.attr
        )
    if rule == "no_db_writes":
        return _is_attr_call(WRITE_ATTRS)
    if rule == "no_raw_sql":
        attr_pred, name_pred = _is_attr_call(RAW_SQL_ATTRS), _is_name(RAW_SQL_NAMES)
        return lambda n: attr_pred(n) or name_pred(n)
    if rule == "no_python_materialization":
        return lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in MATERIALIZE_NAMES
    return None


def module_rule_delta(cand: ast.Module, orig: Optional[ast.Module], rules: List[str]) -> Tuple[List[str], List[str]]:
    """Rules checked on a whole file: a violation is a construct the patch *adds* (count rises)."""
    hard: List[str] = []
    soft: List[str] = []
    for rule in rules:
        pred = _rule_predicates(rule)
        if pred is None:
            continue
        added = _count(cand, pred) - (_count(orig, pred) if orig is not None else 0)
        if added > 0:
            target = soft if rule == "no_python_materialization" else hard
            target.append(f"{rule}: patch adds {added} such construct(s)")
    return hard, soft


def changed_functions(original: str, candidate: str) -> Optional[List[str]]:
    """Dotted names of functions whose source differs; None if code outside functions differs too."""
    orig_tree, cand_tree = parse_or_none(original), parse_or_none(candidate)
    if orig_tree is None or cand_tree is None:
        return None

    def functions(tree, text):
        out = {}
        rest = []

        def visit(nodes, prefix):
            for node in nodes:
                if isinstance(node, FUNC_TYPES):
                    out[".".join(prefix + [node.name])] = ast.get_source_segment(text, node)
                elif isinstance(node, ast.ClassDef):
                    header = (node.name, node.bases, node.keywords, node.decorator_list)
                    rest.append(repr([_dump(part) for part in header]))
                    visit(node.body, prefix + [node.name])
                else:
                    rest.append(ast.dump(node, include_attributes=False))

        visit(tree.body, [])
        return out, rest

    (before, rest_before), (after, rest_after) = functions(orig_tree, original), functions(cand_tree, candidate)
    if set(before) != set(after) or rest_before != rest_after:
        return None
    return sorted(name for name in before if before[name] != after[name])


# ======================================================================
# module: quarry.spec
# ======================================================================

"""Problem statement → TaskSpec, deterministically (regex + markdown structure)."""


import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh", "terminal"}
RUNNERS = (
    "python", "python3", "pytest", "ruff", "go", "npm", "npx", "pnpm", "yarn", "node", "make", "cargo",
    "bundle", "rake", "mvn", "gradle", "./gradlew", "psql", "clickhouse-client", "uv", "poetry", "tox",
    "mypy", "tsc", "vitest", "jest", "flake8", "black", "php", "composer", "dotnet", "mix",
)
FILE_EXTS = (
    ".py", ".go", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sql", ".rb", ".java", ".kt", ".rs", ".php",
    ".cs", ".ex", ".exs", ".prisma", ".yaml", ".yml", ".toml", ".json",
)
BOUNDING = re.compile(
    r"(limit|restrict|confine)\s+(all\s+)?(production\s+)?(code\s+)?changes\s+to"
    r"|you\s+may\s+(only\s+)?edit\s+only|you\s+may\s+only\s+edit|only\s+edit|edit\s+only"
    r"|change\s+only|only\s+change|modify\s+only|only\s+modify|fix\s+only|only\s+fix",
    re.IGNORECASE,
)
NEGATIVE = re.compile(r"\b(do not|don't|never|no|without|must not|avoid|not allowed)\b", re.IGNORECASE)
FORBIDDEN_RULES = (
    ("no_loops", re.compile(r"\bloops?\b", re.I)),
    ("no_comprehensions", re.compile(r"comprehensions?", re.I)),
    ("no_lambdas", re.compile(r"\blambdas?\b", re.I)),
    ("no_exception_handling", re.compile(r"exception[- ]handling|try/except|try-except", re.I)),
    ("no_context_managers", re.compile(r"context[- ]managers?", re.I)),
    ("no_db_writes", re.compile(r"database writes?|db writes?", re.I)),
    ("no_raw_sql", re.compile(r"\braw sql\b", re.I)),
    ("no_dynamic_code", re.compile(r"dynamic[- ]code", re.I)),
    ("no_python_materialization", re.compile(r"materiali[sz]e", re.I)),
)
KIND_WORDS = {
    "optimization": (
        r"optimi[sz]", r"scalab", r"faster", r"\bslow", r"expensive", r"bounded number", r"\bscales?\b", r"grows? with",
        r"\bindex\b", r"\bscan", r"query count", r"buffers?", r"n\+1", r"performance", r"latency",
        r"read_rows", r"selective",
    ),
    "repair": (
        r"\brepair", r"\bfix", r"\bwrong\b", r"incorrect", r"omits?", r"truncat", r"\bbug", r"regress",
        r"broken", r"double[- ]count", r"silently", r"duplicat", r"missing", r"inflat",
    ),
    "authoring": (
        r"\bauthor", r"\bimplement", r"placeholder", r"add support", r"new endpoint", r"\bwrite the\b",
        r"not yet implemented", r"\bstub", r"\bprovide\b",
    ),
}


@dataclass
class Scope:
    files: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    mode: str = "open"  # "named" | "discover-one-symbol" | "open"
    freeze_signature: bool = False
    freeze_imports: bool = False
    rest_frozen: bool = False
    allow_new_files: bool = False
    allow_test_changes: bool = False
    allow_delete: bool = False
    new_files: List[str] = field(default_factory=list)
    new_file_kind: str = ""  # "migration" | "file" when the statement asks for a new file without naming it


@dataclass
class TaskSpec:
    title: str
    kind: str
    engine: str
    scope: Scope
    requirements: List[str]
    forbidden: List[str]
    forbidden_text: List[str]
    checks: List[str]
    check_templates: List[str]
    statement: str

    def render(self, limit: int = 2500) -> str:
        """Compact numbered checklist, stable across the run (used verbatim in prompts)."""
        lines = [f"TASK: {self.title}", f"Kind: {self.kind} · Engine: {self.engine}"]
        sc = self.scope
        if sc.files or sc.symbols or sc.mode != "open":
            lines.append(f"Scope ({sc.mode}): files={sc.files or '?'} symbols={sc.symbols or '?'}")
            flags = [
                name for name, on in (
                    ("keep signature", sc.freeze_signature),
                    ("rest of file byte-identical", sc.rest_frozen),
                    ("imports frozen; only already-imported names", sc.freeze_imports),
                    ("no new files", not sc.allow_new_files),
                    ("no test changes", not sc.allow_test_changes),
                ) if on
            ]
            lines.append("Constraints: " + "; ".join(flags))
        for i, req in enumerate(self.requirements, 1):
            lines.append(f"R{i}. {req}")
        if self.forbidden:
            lines.append("Forbidden: " + ", ".join(self.forbidden))
        for cmd in self.checks + self.check_templates:
            lines.append(f"Check: {cmd}")
        text = "\n".join(lines)
        return text if len(text) <= limit else text[: limit - 20] + "\n[... truncated]"


def compile_statement(statement: str, repo_root: Optional[str] = None) -> TaskSpec:
    text = statement.replace("\r\n", "\n")
    code_blocks = list(re.finditer(r"```([^\n`]*)\n(.*?)```", text, re.S))
    prose = text
    for block in reversed(code_blocks):
        prose = prose[: block.start()] + "\n" + prose[block.end():]

    checks = _block_checks(code_blocks)
    inline_checks, templates = _inline_checks(prose)
    for cmd in inline_checks:
        if cmd not in checks:
            checks.append(cmd)

    paragraphs = [p for p in re.split(r"\n\s*\n", prose) if p.strip()]
    scope = _scope(paragraphs, prose, repo_root)
    forbidden, forbidden_text = _forbidden(prose)
    return TaskSpec(
        title=_title(text),
        kind=_kind(text),
        engine=_engine(text),
        scope=scope,
        requirements=_bullets(prose),
        forbidden=forbidden,
        forbidden_text=forbidden_text,
        checks=checks,
        check_templates=templates,
        statement=statement,
    )


def _title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    if match:
        return match.group(1).strip()
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first[:120]


SHELL_STARTERS = RUNNERS + ("cd", "export", "set", "source", ".", "bash", "sh", "env", "docker", "git")


def _block_checks(blocks) -> List[str]:
    """Each shell block is kept as one script (cd/export/quoting preserved). Untyped blocks must look like shell."""
    checks: List[str] = []
    for block in blocks:
        lang = block.group(1).strip().lower()
        if lang not in SHELL_LANGS:
            continue
        lines = [line[2:] if line.lstrip().startswith("$ ") else line for line in block.group(2).splitlines()]
        lines = [line.lstrip() if line.lstrip().startswith("$ ") else line for line in lines]
        script = "\n".join(line.rstrip() for line in lines).strip("\n")
        body = [line.strip() for line in script.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not body:
            continue
        if lang == "" and body[0].split(" ", 1)[0] not in SHELL_STARTERS and not body[0].startswith("./"):
            continue
        checks.append(script)
    return checks


def _starts_with_runner(cmd: str) -> bool:
    head = cmd.split(" ", 1)[0]
    return head in RUNNERS or head.endswith("/python") or head.startswith("./")


def _inline_checks(prose: str):
    checks: List[str] = []
    templates: List[str] = []
    for sentence in _sentences(prose):
        if not re.search(r"\b(run|execute|check with|verify with)\b", sentence, re.I):
            continue
        for match in re.finditer(r"`([^`]+)`", sentence):
            cmd = re.sub(r"\s+", " ", match.group(1)).strip()
            if not _starts_with_runner(cmd):
                continue
            after = sentence[match.end(): match.end() + 60].lower()
            if re.search(r"on (the|each|every|any) (file|files)( you (changed|edited|modified))?", after):
                templates.append(cmd + " {changed_files}")
            else:
                checks.append(cmd)
    return checks, templates


def _sentences(prose: str) -> List[str]:
    flat = re.sub(r"\s*\n\s*", " ", prose)
    # Split on sentence ends that are outside backticks.
    parts, buf, in_tick = [], [], False
    for i, ch in enumerate(flat):
        buf.append(ch)
        if ch == "`":
            in_tick = not in_tick
        elif ch in ".;:!?" and not in_tick and (i + 1 == len(flat) or flat[i + 1] == " "):
            parts.append("".join(buf).strip())
            buf = []
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _looks_like_path(token: str, repo_root: Optional[str]) -> bool:
    if " " in token or token.startswith("-"):
        return False
    bare = token.rstrip("/")
    if bare.lower().endswith(FILE_EXTS) and not bare.endswith("()"):
        return True
    return bool(repo_root) and "/" in bare and os.path.isfile(os.path.join(repo_root, bare.lstrip("/")))


SYMBOL = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_]\w*)*(\(\))?$")


def _scope(paragraphs: List[str], prose: str, repo_root: Optional[str]) -> Scope:
    scope = Scope()
    for para in paragraphs:
        if not BOUNDING.search(para):
            continue
        for match in re.finditer(r"`([^`]+)`", para):
            token = re.sub(r"\s+", "", match.group(1))
            if _looks_like_path(token, repo_root):
                path = token.lstrip("./") if token.startswith("./") else token
                if path.startswith("/") and repo_root and path.startswith(repo_root.rstrip("/") + "/"):
                    path = path[len(repo_root.rstrip("/")) + 1:]
                if path not in scope.files and not path.startswith("/"):
                    scope.files.append(path)
            elif SYMBOL.match(token) and ("." in token or token.endswith("()")):
                name = token[:-2] if token.endswith("()") else token
                if name not in scope.symbols:
                    scope.symbols.append(name)
    flat = re.sub(r"\s+", " ", prose)
    if scope.symbols:
        scope.mode = "named"
    elif re.search(r"(change|modify|edit) only (that|this|the) (method|function)", flat, re.I):
        scope.mode = "discover-one-symbol"
    elif scope.files:
        scope.mode = "named"
    scope.freeze_signature = bool(re.search(r"keep (its|the|their) (method |function )?signatures?", flat, re.I))
    scope.rest_frozen = bool(
        re.search(r"rest of (the|its|that) file (unchanged|as it is)|everything else in (that|the) file stays", flat, re.I)
        or re.search(r"all unrelated source", flat, re.I)
    )
    scope.freeze_imports = bool(re.search(r"including imports|names the file already imports", flat, re.I))
    positive_new = re.search(r"\b(add|create|write|generate)\s+(a\s+)?(new\s+)?(schema\s+)?(migration|file|module)\b", flat, re.I)
    scope.allow_new_files = bool(positive_new) and not NEGATIVE.search(_sentence_around(flat, positive_new.start()))
    if scope.allow_new_files:
        scope.new_file_kind = "migration" if positive_new.group(5).lower() == "migration" else "file"
    positive_test = re.search(r"\b(add|write|extend)\s+(a\s+)?(regression\s+)?tests?\b", flat, re.I)
    scope.allow_test_changes = bool(positive_test) and not NEGATIVE.search(_sentence_around(flat, positive_test.start()))
    positive_delete = re.search(r"\b(delete|remove)\s+(the\s+)?(obsolete\s+|old\s+|unused\s+)?(file|module)s?\b", flat, re.I)
    scope.allow_delete = bool(positive_delete) and not NEGATIVE.search(_sentence_around(flat, positive_delete.start()))
    if scope.allow_new_files:
        for sentence in _sentences(prose):
            if re.search(r"\b(add|create|write|generate)\b", sentence, re.I) and not NEGATIVE.search(sentence):
                for match in re.finditer(r"`([^`]+)`", sentence):
                    token = re.sub(r"\s+", "", match.group(1))
                    if _looks_like_path(token, None) and not (repo_root and os.path.exists(os.path.join(repo_root, token))):
                        path = token[2:] if token.startswith("./") else token
                        if path not in scope.new_files and not path.startswith("/"):
                            scope.new_files.append(path)
    if scope.symbols or scope.mode == "discover-one-symbol":
        scope.rest_frozen = True  # "change only f()" / "change only that method" excludes the rest of the file
    return scope


def _sentence_around(flat: str, index: int) -> str:
    start = max(flat.rfind(". ", 0, index), flat.rfind(": ", 0, index))
    end = flat.find(". ", index)
    return flat[start + 1: end if end != -1 else len(flat)]


def _forbidden(prose: str):
    rules: List[str] = []
    texts: List[str] = []
    for sentence in _sentences(prose):
        if not NEGATIVE.search(sentence):
            continue
        hit = False
        for rule, pattern in FORBIDDEN_RULES:
            if pattern.search(sentence) and rule not in rules:
                rules.append(rule)
                hit = True
        if hit or re.match(r"\s*(do not|don't|never)\b", sentence, re.I):
            texts.append(sentence)
    return rules, texts


def _kind(text: str) -> str:
    title = _title(text).lower()
    body = text.lower()
    tally = {}
    for kind, words in KIND_WORDS.items():
        count = 0
        for word in words:
            count += 3 * len(re.findall(word, title)) + len(re.findall(word, body))
        tally[kind] = count
    best = max(tally.values())
    if best == 0:
        return "repair"
    for kind in ("repair", "optimization", "authoring"):
        if tally[kind] == best:
            return kind
    return "repair"


def _engine(text: str) -> str:
    low = text.lower()
    if "clickhouse" in low or "mergetree" in low:
        return "clickhouse"
    if re.search(r"postgres|\bpsql\b|\bpg_|jsonb|\bplpgsql\b", low):
        return "postgresql"
    return "unknown"


def _bullets(prose: str) -> List[str]:
    items: List[str] = []
    current: Optional[List[str]] = None
    for line in prose.splitlines():
        match = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if match:
            if current:
                items.append(" ".join(current))
            current = [match.group(1).strip()]
        elif current is not None and line.strip() and line.startswith((" ", "\t")):
            current.append(line.strip())
        else:
            if current:
                items.append(" ".join(current))
            current = None
    if current:
        items.append(" ".join(current))
    return [re.sub(r"[;,]?\s*(and)?\s*$", "", item).strip() for item in items]


# ======================================================================
# module: quarry.scope
# ======================================================================

"""One statement-derived scope policy shared by the edit tools and the guard: what may be edited, created, deleted."""


import os
import re
from typing import List, Optional, Tuple


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


# ======================================================================
# module: quarry.guard
# ======================================================================

"""Deterministic patch hygiene: repairs that bring the tree back into scope, then checks that gate a candidate."""


import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple



@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    hard: bool = True


@dataclass
class GuardReport:
    repairs: List[str] = field(default_factory=list)
    results: List[CheckResult] = field(default_factory=list)
    diff: str = ""

    @property
    def eligible(self) -> bool:
        return all(r.ok for r in self.results if r.hard)

    def failures(self) -> List[CheckResult]:
        return [r for r in self.results if not r.ok]

    def render(self) -> str:
        lines = [f"repair: {note}" for note in self.repairs]
        for r in self.results:
            status = "PASS" if r.ok else ("FAIL" if r.hard else "WARN")
            lines.append(f"{status} {r.name}: {r.detail}")
        return "\n".join(lines)


class GuardContext:
    """What repairs and checks need. `target` is a (file, symbol) the workflow located when the statement named none."""

    def __init__(self, repo: GitRepo, spec: TaskSpec, target: Optional[Tuple[str, str]] = None):
        self.repo = repo
        self.spec = spec
        self.target = target
        self.policy = ScopePolicy(spec, target)
        self.changes: ChangeSet = repo.changed()

    def refresh(self) -> None:
        self.changes = self.repo.changed()

    @property
    def scope_files(self) -> List[str]:
        return self.policy.files

    def symbols_for(self, path: str) -> List[str]:
        """Scope symbols that live in `path` (resolved against HEAD)."""
        if not path.endswith(".py"):
            return []
        tree = parse_or_none(self.repo.head_text(path))
        if tree is None:
            return []
        wanted = self.policy.symbols
        resolved: List[str] = []
        for name in wanted:
            if find_symbol(tree, name) is not None:
                resolved.append(name)
            else:
                matches = find_symbol_anywhere(tree, name.split(".")[-1])
                if len(matches) == 1:
                    resolved.append(matches[0])
        return resolved

    def read(self, path: str) -> Optional[str]:
        try:
            with open(os.path.join(self.repo.root, path), encoding="utf-8", newline="") as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError):
            return None

    def write(self, path: str, text: str) -> None:
        with open(os.path.join(self.repo.root, path), "w", encoding="utf-8", newline="") as handle:
            handle.write(text)


# ---------------------------------------------------------------- repairs


class RevertTestChanges:
    name = "revert-test-changes"

    def apply(self, ctx: GuardContext) -> List[str]:
        if ctx.spec.scope.allow_test_changes:
            return []
        notes = []
        for path in ctx.changes.modified + ctx.changes.deleted + ctx.changes.added + ctx.changes.untracked:
            if ctx.policy.is_test(path) and path not in ctx.scope_files:
                ctx.repo.restore(path)
                notes.append(f"reverted test file {path}")
        return notes


class RevertOutOfScope:
    name = "revert-out-of-scope"

    def apply(self, ctx: GuardContext) -> List[str]:
        notes = []
        for path in ctx.changes.modified:
            if ctx.policy.edit_refusal(path):
                ctx.repo.restore(path)
                notes.append(f"reverted out-of-scope {path}")
        for path in ctx.changes.deleted:
            if ctx.policy.delete_refusal(path) or ctx.policy.edit_refusal(path):
                ctx.repo.restore(path)
                notes.append(f"restored deleted file {path}")
        return notes


class DropUntracked:
    name = "drop-untracked"

    def apply(self, ctx: GuardContext) -> List[str]:
        notes = []
        for path in ctx.changes.untracked + ctx.changes.added:
            if not ctx.policy.create_refusal(path):
                ctx.repo.intent_to_add(path)
                notes.append(f"kept new file {path}")
            else:
                ctx.repo.restore(path)
                notes.append(f"removed new file {path}")
        return notes


class RestoreModes:
    name = "restore-modes"

    def apply(self, ctx: GuardContext) -> List[str]:
        notes = []
        for path in ctx.changes.mode_changed:
            ctx.repo.restore_mode(path)
            notes.append(f"restored mode of {path}")
        return notes


class SpliceBoundedSymbols:
    name = "splice-bounded-symbols"

    def apply(self, ctx: GuardContext) -> List[str]:
        if not ctx.spec.scope.rest_frozen:
            return []
        notes = []
        for path in ctx.changes.modified:
            symbols = ctx.symbols_for(path)
            original = ctx.repo.head_text(path)
            candidate = ctx.read(path)
            if not symbols or original is None or candidate is None:
                continue
            text = original
            for symbol in symbols:
                spliced = splice(text, candidate, symbol)
                if spliced is not None:
                    text = spliced
            if text != candidate:
                ctx.write(path, text)
                notes.append(f"restored text outside {', '.join(symbols)} in {path}")
        return notes


# ---------------------------------------------------------------- checks


class ScopeCheck:
    name = "scope"

    def run(self, ctx: GuardContext) -> CheckResult:
        policy = ctx.policy
        problems = [f"{p}: {policy.edit_refusal(p)}" for p in ctx.changes.modified if policy.edit_refusal(p)]
        problems += [f"{p} deleted: {policy.delete_refusal(p)}" for p in ctx.changes.deleted if policy.delete_refusal(p)]
        new = ctx.changes.added + ctx.changes.untracked
        problems += [f"{p}: {policy.create_refusal(p)}" for p in new if policy.create_refusal(p)]
        if ctx.spec.scope.mode == "discover-one-symbol" and not ctx.spec.scope.files:
            prod = [p for p in ctx.changes.modified + ctx.changes.deleted if not policy.is_test(p)]
            if len(prod) > 1:
                problems.append(f"the statement allows one method in one file; changed {prod}")
        if problems:
            return CheckResult(self.name, False, "; ".join(problems))
        return CheckResult(self.name, True, f"{len(ctx.changes.modified)} changed, {len(new)} new")


class ModeCheck:
    name = "file-modes"

    def run(self, ctx: GuardContext) -> CheckResult:
        if ctx.changes.mode_changed:
            return CheckResult(self.name, False, f"mode changed: {sorted(ctx.changes.mode_changed)}")
        return CheckResult(self.name, True, "no mode changes")


class PythonCompiles:
    name = "python-compiles"

    def run(self, ctx: GuardContext) -> CheckResult:
        for path in ctx.changes.modified + ctx.changes.added + ctx.changes.untracked:
            if path.endswith(".py"):
                text = ctx.read(path)
                try:
                    compile(text or "", path, "exec", dont_inherit=True)
                except SyntaxError as exc:
                    return CheckResult(self.name, False, f"{path}:{exc.lineno}: {exc.msg}")
        return CheckResult(self.name, True, "ok")


class BoundedSymbolCheck:
    name = "bounded-symbol"

    def run(self, ctx: GuardContext) -> CheckResult:
        if not ctx.spec.scope.rest_frozen:
            return CheckResult(self.name, True, "statement does not bound the change to a symbol")
        named = ctx.policy.symbols
        for path in ctx.changes.deleted:
            if path in ctx.scope_files:
                return CheckResult(self.name, False, f"{path} was deleted; only its named symbols may change")
        unchecked = []
        for path in ctx.changes.modified:
            if not path.endswith(".py"):
                if named:
                    unchecked.append(path)
                continue
            original, candidate = ctx.repo.head_text(path), ctx.read(path)
            if original is None or candidate is None:
                continue
            symbols = ctx.symbols_for(path)
            if named and not symbols and path in ctx.scope_files:
                return CheckResult(self.name, False, f"{path} changed but none of {named} is defined there")
            if not symbols and ctx.spec.scope.mode == "discover-one-symbol":
                changed = changed_functions(original, candidate)
                if changed is None or len(changed) != 1:
                    return CheckResult(self.name, False, f"{path}: expected exactly one changed method, got {changed}")
                symbols = changed
            if not symbols:
                continue
            if len(symbols) == 1:
                ok, detail = outside_identical(original, candidate, symbols[0])
                if not ok:
                    return CheckResult(self.name, False, f"{path}: {detail}")
                continue
            rebuilt = original
            for symbol in symbols:
                rebuilt = splice(rebuilt, candidate, symbol) or rebuilt
            if rebuilt != candidate:
                return CheckResult(self.name, False, f"{path}: text outside {symbols} changed")
        if unchecked:
            return CheckResult(self.name, False, f"symbol bounds not inspected for {unchecked} (no parser for this language)", hard=False)
        return CheckResult(self.name, True, "only the bounded symbols changed")


class _SymbolPairCheck:
    """Base for checks that compare baseline and candidate versions of each bounded symbol."""

    name = "symbol-pair"

    def pairs(self, ctx: GuardContext):
        for path in ctx.changes.modified:
            original, candidate = ctx.repo.head_text(path), ctx.read(path)
            orig_tree, cand_tree = parse_or_none(original), parse_or_none(candidate)
            if orig_tree is None or cand_tree is None:
                continue
            for symbol in self.symbols(ctx, path, original or "", candidate or ""):
                orig_node, cand_node = find_symbol(orig_tree, symbol), find_symbol(cand_tree, symbol)
                if orig_node is not None and cand_node is not None:
                    yield path, symbol, orig_tree, cand_tree, orig_node, cand_node

    @staticmethod
    def symbols(ctx: GuardContext, path: str, original: str, candidate: str) -> List[str]:
        symbols = ctx.symbols_for(path)
        if not symbols and ctx.spec.scope.mode == "discover-one-symbol":
            symbols = changed_functions(original, candidate) or []
        return symbols


class SignatureCheck(_SymbolPairCheck):
    name = "signature"

    def run(self, ctx: GuardContext) -> CheckResult:
        if not ctx.spec.scope.freeze_signature:
            return CheckResult(self.name, True, "not required")
        for path, symbol, _ot, _ct, orig_node, cand_node in self.pairs(ctx):
            ok, detail = header_equal(orig_node, cand_node)
            if not ok:
                return CheckResult(self.name, False, f"{path}:{symbol}: {detail}")
        return CheckResult(self.name, True, "unchanged")


class ImportsCheck(_SymbolPairCheck):
    name = "imports"

    def run(self, ctx: GuardContext) -> CheckResult:
        if not ctx.spec.scope.freeze_imports:
            return CheckResult(self.name, True, "not required")
        for path in ctx.changes.modified:
            orig_tree = parse_or_none(ctx.repo.head_text(path))
            cand_tree = parse_or_none(ctx.read(path))
            if orig_tree is not None and cand_tree is not None and module_imports(orig_tree) != module_imports(cand_tree):
                return CheckResult(self.name, False, f"{path}: module imports changed")
        for path, symbol, _ot, cand_tree, _on, cand_node in self.pairs(ctx):
            missing = unbound_names(cand_node, cand_tree)
            if missing:
                return CheckResult(self.name, False, f"{path}:{symbol} uses names the file does not import: {missing}")
        return CheckResult(self.name, True, "imports unchanged; all names bound")


class ConstructRulesCheck(_SymbolPairCheck):
    """Statement rules on the bounded symbols; without named symbols, on everything the patch adds to each file."""

    name = "statement-rules"

    def run(self, ctx: GuardContext) -> CheckResult:
        rules = ctx.spec.forbidden
        if not rules:
            return CheckResult(self.name, True, "no construct rules in the statement")
        hard_all: List[str] = []
        soft_all: List[str] = []
        unchecked: List[str] = []
        inspected = 0
        for path in ctx.changes.modified + ctx.changes.added + ctx.changes.untracked:
            if not path.endswith(".py"):
                unchecked.append(path)
                continue
            original, candidate = ctx.repo.head_text(path), ctx.read(path)
            orig_tree, cand_tree = parse_or_none(original), parse_or_none(candidate)
            if cand_tree is None:
                continue
            symbols = self.symbols(ctx, path, original or "", candidate or "") if orig_tree is not None else []
            if symbols:
                for symbol in symbols:
                    orig_node, cand_node = find_symbol(orig_tree, symbol), find_symbol(cand_tree, symbol)
                    if cand_node is None:
                        continue
                    inspected += 1
                    hard, soft = rule_violations(cand_node, orig_node, rules)
                    hard_all += [f"{path}:{symbol}: {h}" for h in hard]
                    soft_all += [f"{path}:{symbol}: {s}" for s in soft]
            else:
                inspected += 1
                hard, soft = module_rule_delta(cand_tree, orig_tree, rules)
                hard_all += [f"{path}: {h}" for h in hard]
                soft_all += [f"{path}: {s}" for s in soft]
        if hard_all:
            return CheckResult(self.name, False, "; ".join(hard_all))
        if unchecked:
            soft_all.append(f"rules not inspected for {unchecked} (no parser for this language)")
        if soft_all:
            return CheckResult(self.name, False, "; ".join(soft_all), hard=False)
        return CheckResult(self.name, True, f"ok ({inspected} unit(s) inspected)")


class NonEmptyCheck:
    name = "non-empty"

    def run(self, ctx: GuardContext) -> CheckResult:
        diff = ctx.repo.diff()
        body = [
            line[1:] for line in diff.splitlines()
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        if not body:
            return CheckResult(self.name, False, "diff is empty")
        if all(not line.strip() for line in body) or _whitespace_only(diff, ctx):
            return CheckResult(self.name, False, "diff changes whitespace only")
        return CheckResult(self.name, True, f"{len(body)} changed lines")


def _whitespace_only(diff: str, ctx: GuardContext) -> bool:
    result = ctx.repo.git("diff", "-w", "--ignore-blank-lines", ctx.repo.base)
    return result.ok and not result.output.strip() and bool(diff.strip())


class ApplyCheck:
    name = "apply-check"

    def run(self, ctx: GuardContext) -> CheckResult:
        result = ctx.repo.apply_check(ctx.repo.diff())
        return CheckResult(self.name, result.ok, "applies to a clean tree" if result.ok else result.output[-500:])


DEFAULT_REPAIRS: Sequence = (RevertTestChanges(), RevertOutOfScope(), DropUntracked(), RestoreModes(), SpliceBoundedSymbols())
DEFAULT_CHECKS: Sequence = (
    ScopeCheck(), ModeCheck(), PythonCompiles(), BoundedSymbolCheck(), SignatureCheck(), ImportsCheck(),
    ConstructRulesCheck(), NonEmptyCheck(), ApplyCheck(),
)


class Guard:
    def __init__(self, repairs: Sequence = DEFAULT_REPAIRS, checks: Sequence = DEFAULT_CHECKS):
        self.repairs = list(repairs)
        self.checks = list(checks)

    def run(self, ctx: GuardContext, repair: bool = True) -> GuardReport:
        report = GuardReport()
        if repair:
            for step in self.repairs:
                ctx.refresh()
                report.repairs.extend(step.apply(ctx))
        ctx.refresh()
        for check in self.checks:
            try:
                report.results.append(check.run(ctx))
            except Exception as exc:  # a broken check must not crash the run
                report.results.append(CheckResult(check.name, False, f"check error: {exc}"))
        report.diff = ctx.repo.diff()
        return report


# ======================================================================
# module: quarry.wallet
# ======================================================================

"""Inference budget: a hard cap from the environment, per-phase caps, reservations and cost provenance.

Every model attempt reserves its pre-call estimate. The reservation is then settled as:
- "provider": the response reported its cost;
- "estimate": the response reported token usage but no cost (priced from the table, labelled as such);
- "unknown":  no usable report (e.g. a timeout after sending); the reservation stays consumed;
- "none":     evidence of no charge (connection refused, request rejected with an error response); released.
Spending checks use everything consumed, including unknown reservations; reports keep the categories apart.
"""


import os
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Tuple

DEFAULT_CAP_USD = 0.29
SPENDABLE_SHARE = 0.9
# (input, output) USD per 1M tokens. Unknown models fall back to a conservative price.
FALLBACK_PRICE = (3.0, 15.0)


class BudgetExhausted(Exception):
    """Raised when a call would exceed the budget, or the provider refused on cost grounds."""


def read_cap_env(environ: Optional[dict] = None) -> float:
    env = os.environ if environ is None else environ
    try:
        value = float(str(env.get("RIDGES_MAX_COST_USD", "")).strip())
    except ValueError:
        return DEFAULT_CAP_USD
    return value if value > 0 else DEFAULT_CAP_USD


class Reservation:
    def __init__(self, amount: float, phase: Optional[str]):
        self.amount = amount
        self.phase = phase
        self.settled = False


class Wallet:
    def __init__(self, cap_usd: float, prices: Optional[Dict[str, Tuple[float, float]]] = None):
        self.cap = float(cap_usd)
        self.spendable = self.cap * SPENDABLE_SHARE
        self.spent = False
        self.prices = dict(prices or {})
        self.provider_usd = 0.0
        self.estimate_usd = 0.0
        self.unknown_usd = 0.0  # reservations kept for attempts whose cost is unknown
        self.estimated_calls = 0
        self.unknown_attempts = 0
        self.pending_usd = 0.0  # reservations not yet settled
        self._phase_name: Optional[str] = None
        self._phase_cap: Optional[float] = None
        self._phase_spent = 0.0
        self.by_phase: Dict[str, float] = {}

    @classmethod
    def from_env(cls, environ: Optional[dict] = None, prices: Optional[dict] = None) -> Wallet:
        return cls(read_cap_env(environ), prices)

    # -------------------------------------------------------------- amounts

    @property
    def consumed_usd(self) -> float:
        """Everything that counts against the budget: reported, estimated and unknown-but-reserved."""
        return self.provider_usd + self.estimate_usd + self.unknown_usd

    @property
    def spent_usd(self) -> float:  # kept for callers that only need one number for budget decisions
        return self.consumed_usd

    @property
    def accounting_complete(self) -> bool:
        return self.unknown_attempts == 0

    def price(self, model: str) -> Tuple[float, float]:
        return self.prices.get(model, FALLBACK_PRICE)

    def estimate(self, model: str, prompt_tokens: int, max_tokens: int) -> float:
        price_in, price_out = self.price(model)
        return (prompt_tokens * price_in + max_tokens * price_out) / 1_000_000

    def remaining(self) -> float:
        used = self.consumed_usd + self.pending_usd
        left = self.spendable - used
        if self._phase_cap is not None:
            left = min(left, self._phase_cap - self._phase_spent)
        return max(0.0, left)

    def can_afford(self, estimate_usd: float) -> bool:
        return not self.spent and estimate_usd <= self.remaining()

    def ensure(self, estimate_usd: float) -> None:
        if self.spent:
            raise BudgetExhausted("budget already exhausted")
        if not self.can_afford(estimate_usd):
            raise BudgetExhausted(f"estimated ${estimate_usd:.4f} exceeds remaining ${self.remaining():.4f}")

    # -------------------------------------------------------------- attempt lifecycle

    def reserve(self, estimate_usd: float) -> Reservation:
        """Reserve an attempt's estimate before sending it; refuses when it does not fit."""
        self.ensure(estimate_usd)
        self.pending_usd += estimate_usd
        self._phase_spent += estimate_usd
        return Reservation(estimate_usd, self._phase_name)

    def _close(self, reservation: Reservation) -> None:
        if reservation.settled:
            raise ValueError("reservation already settled")
        reservation.settled = True
        self.pending_usd = max(0.0, self.pending_usd - reservation.amount)
        if reservation.phase == self._phase_name:
            self._phase_spent -= reservation.amount

    def _book(self, reservation: Reservation, amount: float) -> None:
        if reservation.phase == self._phase_name:
            self._phase_spent += amount
        if reservation.phase:
            self.by_phase[reservation.phase] = self.by_phase.get(reservation.phase, 0.0) + amount

    def settle(self, reservation: Reservation, model: str, usage: Optional[dict]) -> Tuple[Optional[float], str]:
        """Replace the reservation with the reported cost, or a labelled usage-based estimate, or keep it as unknown."""
        self._close(reservation)
        usage = usage if isinstance(usage, dict) else {}
        cost = usage.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            self.provider_usd += float(cost)
            self._book(reservation, float(cost))
            return float(cost), "provider"
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if isinstance(prompt, int) and isinstance(completion, int):
            price_in, price_out = self.price(model)
            estimated = (prompt * price_in + completion * price_out) / 1_000_000
            self.estimate_usd += estimated
            self.estimated_calls += 1
            self._book(reservation, estimated)
            return estimated, "estimate"
        return self.keep_unknown(reservation, already_closed=True)

    def keep_unknown(self, reservation: Reservation, already_closed: bool = False) -> Tuple[Optional[float], str]:
        """No usable report (e.g. timeout after sending): the reservation stays consumed; the real cost is unknown."""
        if not already_closed:
            self._close(reservation)
        self.unknown_usd += reservation.amount
        self.unknown_attempts += 1
        self._book(reservation, reservation.amount)
        return None, "unknown"

    def release(self, reservation: Reservation) -> Tuple[Optional[float], str]:
        """Evidence of no charge (never sent, or rejected with an error response): give the reservation back."""
        self._close(reservation)
        return 0.0, "none"

    def charge(self, model: str, usage: Optional[dict]) -> float:
        """One-step reserve-and-settle for a completed response (no pre-call reservation available)."""
        reservation = Reservation(0.0, self._phase_name)
        cost, _source = self.settle(reservation, model, usage)
        return cost if cost is not None else 0.0

    def mark_spent(self) -> None:
        self.spent = True

    @contextmanager
    def phase(self, name: str, cap_usd: float) -> Iterator[Wallet]:
        """Limit spending to `cap_usd` inside the block (nested phases are not supported)."""
        saved = (self._phase_name, self._phase_cap, self._phase_spent)
        self._phase_name, self._phase_cap, self._phase_spent = name, float(cap_usd), 0.0
        try:
            yield self
        finally:
            self._phase_name, self._phase_cap, self._phase_spent = saved

    def summary(self) -> Dict[str, object]:
        return {
            "provider_usd": round(self.provider_usd, 6),
            "estimate_usd": round(self.estimate_usd, 6),
            "estimated_calls": self.estimated_calls,
            "unknown_attempts": self.unknown_attempts,
            "unknown_reserved_usd": round(self.unknown_usd, 6),
            "accounted_usd": round(self.provider_usd + self.estimate_usd, 6),
            "consumed_usd": round(self.consumed_usd, 6),
            "cost_estimated": self.estimated_calls > 0,
            "accounting_complete": self.accounting_complete,
        }


def is_budget_refusal(status: int, body: str) -> bool:
    """True when a provider response means the cost cap was hit (never worth retrying)."""
    if status == 402:
        return True
    text = (body or "").lower()
    return status in (400, 403, 429) and any(
        marker in text for marker in ("budget", "cost cap", "max cost", "spend limit", "insufficient credit")
    )


# ======================================================================
# module: quarry.llm
# ======================================================================

"""Chat-completions client for the inference proxy: retries, model fallback, budget checks, telemetry."""


import json
import os
import random
import socket
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}
MAX_ATTEMPTS = 4
MIN_ATTEMPT_SEC = 5.0  # an attempt with less time than this is not worth starting
DEFAULT_PROXY = "http://sandbox-proxy:80"  # documented default of SANDBOX_PROXY_URL


class LLMError(Exception):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict
    error: str = ""  # set when the arguments were not valid JSON


@dataclass
class ChatResult:
    content: str
    tool_calls: List[ToolCall]
    usage: Dict
    model: str
    message: Dict  # assistant message to append to the transcript


@dataclass
class CallRecord:
    """One attempt. Token and cost fields are None when the response did not report them (never coerced to 0)."""

    role: str
    model: str
    status: int
    latency: float
    cost: Optional[float]
    cost_source: str  # provider | estimate | unknown | none (see wallet.py)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    cache_discount: Optional[float] = None
    ok: bool = True
    note: str = ""


def _opt_int(value) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def usage_fields(usage) -> Dict:
    """Token and cache fields exactly as reported; missing stays None."""
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    discount = usage.get("cache_discount")
    return {
        "prompt_tokens": _opt_int(usage.get("prompt_tokens")),
        "completion_tokens": _opt_int(usage.get("completion_tokens")),
        "cached_tokens": _opt_int(details.get("cached_tokens")),
        "cache_write_tokens": _opt_int(details.get("cache_write_tokens")),
        "cache_discount": float(discount) if isinstance(discount, (int, float)) and not isinstance(discount, bool) else None,
    }


def _never_sent(exc: BaseException) -> bool:
    """True when the request certainly never reached the provider (so it cannot have been charged)."""
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (ConnectionRefusedError, socket.gaierror))


def resolve_endpoint(environ: Optional[dict] = None) -> Tuple[str, str]:
    """(chat completions URL, bearer key). Production proxy first, then the local-run helper."""
    env = os.environ if environ is None else environ
    base = (env.get("RIDGES_INFERENCE_BASE_URL") or "").rstrip("/")
    if base and not env.get("SANDBOX_PROXY_URL"):
        return base + "/chat/completions", env.get("RIDGES_INFERENCE_API_KEY", "") or env.get("OPENROUTER_API_KEY", "")
    proxy = (env.get("SANDBOX_PROXY_URL") or DEFAULT_PROXY).rstrip("/")
    return proxy + "/api/v1/chat/completions", env.get("OPENROUTER_API_KEY", "")


def estimate_tokens(messages: List[Dict], tools: Optional[List[Dict]] = None) -> int:
    size = len(json.dumps(messages, ensure_ascii=False))
    if tools:
        size += len(json.dumps(tools))
    return int(size / 3.2) + 50


Transport = Callable[[str, bytes, Dict[str, str], float], Tuple[int, str]]


def urllib_transport(url: str, body: bytes, headers: Dict[str, str], timeout: float) -> Tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def parse_tool_calls(message: Dict) -> List[ToolCall]:
    calls: List[ToolCall] = []
    for raw in message.get("tool_calls") or []:
        fn = raw.get("function") or {}
        name = str(fn.get("name") or "").strip()
        call_id = str(raw.get("id") or "") or "call_" + uuid.uuid4().hex[:12]
        raw["id"] = call_id
        args_text = fn.get("arguments")
        if isinstance(args_text, dict):
            calls.append(ToolCall(call_id, name, args_text))
            continue
        try:
            args = json.loads(args_text or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
            calls.append(ToolCall(call_id, name, args))
        except (ValueError, TypeError) as exc:
            calls.append(ToolCall(call_id, name, {}, error=f"invalid JSON arguments: {exc}"))
    return calls


@dataclass
class ModelRoute:
    model: str
    fallback: Optional[str] = None
    max_tokens: int = 4096
    reasoning: Optional[Dict] = None


class ProxyClient:
    def __init__(
        self,
        wallet: Wallet,
        environ: Optional[dict] = None,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.url, self.key = resolve_endpoint(environ)
        self.wallet = wallet
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.telemetry: List[CallRecord] = []
        self._failures: Dict[str, int] = {}

    def complete(
        self,
        messages: List[Dict],
        route: ModelRoute,
        tools: Optional[List[Dict]] = None,
        role: str = "driver",
        timeout: float = 180.0,
        max_tokens: Optional[int] = None,
        deadline: Optional[float] = None,
    ) -> ChatResult:
        """One completion. `deadline` is an absolute time on `self.clock`; no attempt, wait or backoff passes it."""
        max_out = max_tokens or route.max_tokens
        model = route.model
        if route.fallback and self._failures.get(model, 0) >= 2:
            model = route.fallback
        prompt_est = estimate_tokens(messages, tools)
        last_error = ""
        for attempt in range(MAX_ATTEMPTS):
            attempt_timeout = timeout
            if deadline is not None:
                left = deadline - self.clock()
                if left < MIN_ATTEMPT_SEC:
                    raise LLMError(f"no time left for a model call ({left:.1f}s); last error: {last_error or 'none'}")
                attempt_timeout = min(timeout, left)
            reservation = self.wallet.reserve(self.wallet.estimate(model, prompt_est, max_out))
            body: Dict = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_out, "usage": {"include": True}}
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            if route.reasoning:
                body["reasoning"] = route.reasoning
            headers = {"Content-Type": "application/json"}
            if self.key:
                headers["Authorization"] = "Bearer " + self.key
            started = self.clock()
            never_sent = False
            try:
                status, text = self.transport(self.url, json.dumps(body).encode(), headers, attempt_timeout)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
                status, text = 0, f"transport error: {exc}"
                never_sent = _never_sent(exc)
            latency = self.clock() - started
            usage: Dict = {}
            if status == 200:
                try:
                    data = json.loads(text)
                    choice = (data.get("choices") or [{}])[0]
                    message = choice.get("message") or {}
                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                except (ValueError, AttributeError, IndexError) as exc:
                    status, text = 502, f"unparseable response: {exc}"
                else:
                    if data.get("error"):
                        status, text = int((data["error"] or {}).get("code") or 502), json.dumps(data["error"])
                    else:
                        return self._success(data, message, model, role, latency, reservation)
            # Failed attempt. An HTTP error response means the request was rejected (no charge); a sent request
            # with no usable answer (timeout, reset, broken body) may have been charged: keep its reservation.
            if never_sent or status >= 400:
                cost, source = self.wallet.release(reservation)
            elif usage:
                cost, source = self.wallet.settle(reservation, model, usage)
            else:
                cost, source = self.wallet.keep_unknown(reservation)
            record = CallRecord(role, model, status, latency, cost, source, ok=False, **usage_fields(usage))
            if is_budget_refusal(status, text):
                self.wallet.mark_spent()
                record.note = f"budget refusal {status}"
                self.telemetry.append(record)
                raise BudgetExhausted(f"provider refused on budget grounds ({status})")
            last_error = f"{status}: {text[:300]}"
            record.note = last_error[:120]
            self.telemetry.append(record)
            self._failures[model] = self._failures.get(model, 0) + 1
            retryable = status == 0 or status in RETRY_STATUS
            if not retryable:
                break
            if route.fallback and model != route.fallback and self._failures[model] >= 2:
                model = route.fallback
            pause = min(20.0, (2 ** attempt) + random.random())
            if deadline is not None:
                pause = min(pause, deadline - self.clock() - MIN_ATTEMPT_SEC)
                if pause < 0:
                    break
            self.sleep(pause)
        raise LLMError(f"model call failed after retries: {last_error}")

    def _success(self, data: Dict, message: Dict, model: str, role: str, latency: float, reservation) -> ChatResult:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        cost, source = self.wallet.settle(reservation, model, usage)
        self.telemetry.append(CallRecord(role, model, 200, latency, cost, source, **usage_fields(usage)))
        self._failures[model] = 0
        calls = parse_tool_calls(message)
        assistant = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("tool_calls"):
            assistant["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in calls
            ]
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return ChatResult(content, calls, usage, str(data.get("model") or model), assistant)


# ======================================================================
# module: quarry.profile
# ======================================================================

"""Repository and environment profiling: languages, query layers, databases, tools. No LLM, no app imports."""


import ast
import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional
from urllib.parse import unquote, urlparse

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", "target", "vendor",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next", "coverage", "site-packages", ".tox",
}
TOOLS = ("psql", "clickhouse-client", "clickhouse", "go", "node", "npx", "tsc", "ruff", "pytest", "rg")
LAYER_MARKERS = {
    # layer: (language, regex over manifests/imports)
    "django": ("python", r"\bdjango\b"),
    "sqlalchemy": ("python", r"\bsqlalchemy\b"),
    "alembic": ("python", r"\balembic\b"),
    "peewee": ("python", r"\bpeewee\b"),
    "psycopg": ("python", r"\bpsycopg2?\b|\basyncpg\b"),
    "clickhouse-py": ("python", r"clickhouse[_-](connect|driver)"),
    "gorm": ("go", r"gorm\.io/gorm"),
    "sqlx": ("go", r"jmoiron/sqlx"),
    "pgx": ("go", r"jackc/pgx"),
    "bun": ("go", r"uptrace/bun"),
    "ent": ("go", r"entgo\.io/ent"),
    "clickhouse-go": ("go", r"ClickHouse/clickhouse-go"),
    "database/sql": ("go", r"\"database/sql\""),
    "prisma": ("typescript", r"@prisma/client|\bprisma\b"),
    "typeorm": ("typescript", r"\btypeorm\b"),
    "knex": ("typescript", r"\bknex\b"),
    "drizzle": ("typescript", r"drizzle-orm"),
    "kysely": ("typescript", r"\bkysely\b"),
    "sequelize": ("typescript", r"\bsequelize\b"),
    "clickhouse-js": ("typescript", r"@clickhouse/client"),
    "activerecord": ("ruby", r"\bactiverecord\b|\brails\b"),
}
LANGUAGE_MARKERS = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "manage.py", "Pipfile"),
    "go": ("go.mod",),
    "typescript": ("tsconfig.json",),
    "javascript": ("package.json",),
    "ruby": ("Gemfile",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "rust": ("Cargo.toml",),
    "elixir": ("mix.exs",),
}
MANIFESTS = (
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "go.mod",
    "package.json", "Gemfile", "pom.xml", "build.gradle",
)
DSN = re.compile(r"\b((?:postgres(?:ql)?|clickhouse|clickhouses)(?:\+\w+)?://[^\s'\"`<>]+)")
CONFIG_NAMES = re.compile(
    r"(^|/)(settings[^/]*\.py|configuration[^/]*\.py|config[^/]*\.py|database\.ya?ml|config\.ya?ml|"
    r"application\.ya?ml|alembic\.ini|\.env[^/]*|docker-compose[^/]*\.ya?ml|compose\.ya?ml|.*\.toml)$"
)


@dataclass
class DbTarget:
    engine: str  # "postgresql" | "clickhouse"
    host: str = "localhost"
    port: int = 0
    user: str = ""
    password: str = ""
    name: str = ""
    test_name: str = ""
    source: str = ""

    def describe(self) -> str:
        db = self.name + (f" (test db: {self.test_name})" if self.test_name else "")
        return f"{self.engine} {self.user}@{self.host}:{self.port}/{db} [from {self.source}]"


@dataclass
class EnvProfile:
    root: str
    languages: List[str] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    databases: List[DbTarget] = field(default_factory=list)
    tools: Dict[str, str] = field(default_factory=dict)
    writable: Dict[str, bool] = field(default_factory=dict)
    is_root_user: bool = False

    def engines(self) -> List[str]:
        return sorted({db.engine for db in self.databases})

    def render(self) -> str:
        lines = [
            f"Languages: {', '.join(self.languages) or 'unknown'}",
            f"Query layers: {', '.join(self.layers) or 'unknown'}",
            f"Tools: {', '.join(sorted(self.tools)) or 'none'}",
        ]
        for db in self.databases[:4]:
            lines.append("Database: " + db.describe())
        if self.writable:
            lines.append("Writable scope files: " + ", ".join(f"{p}={'yes' if ok else 'NO'}" for p, ok in self.writable.items()))
        return "\n".join(lines)


def walk_files(root: str, max_files: int = 20000, max_depth: int = 8) -> Iterator[str]:
    """Yield repo-relative file paths, skipping vendored and generated directories."""
    count = 0
    base_depth = root.rstrip("/").count("/")
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count("/") - base_depth
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")] if depth < max_depth else []
        for name in filenames:
            count += 1
            if count > max_files:
                return
            yield os.path.relpath(os.path.join(dirpath, name), root)


def _read(path: str, limit: int = 200_000) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def build_profile(root: str, scope_files: Optional[List[str]] = None, environ: Optional[dict] = None) -> EnvProfile:
    env = os.environ if environ is None else environ
    profile = EnvProfile(root=os.path.abspath(root))
    files = list(walk_files(root))
    names = {os.path.basename(f) for f in files}

    for language, markers in LANGUAGE_MARKERS.items():
        if any(m in names for m in markers):
            profile.languages.append(language)
    if "typescript" in profile.languages and "javascript" in profile.languages:
        profile.languages.remove("javascript")

    manifest_text = "\n".join(_read(os.path.join(root, f)) for f in files if os.path.basename(f) in MANIFESTS)
    for layer, (_language, pattern) in LAYER_MARKERS.items():
        if re.search(pattern, manifest_text, re.I):
            profile.layers.append(layer)
    if "schema.prisma" in names and "prisma" not in profile.layers:
        profile.layers.append("prisma")
    if any(n in names for n in ("sqlc.yaml", "sqlc.yml", "sqlc.json")):
        profile.layers.append("sqlc")

    profile.databases = discover_databases(root, files, env)
    for tool in TOOLS:
        found = shutil.which(tool)
        if found:
            profile.tools[tool] = found
    for rel in scope_files or []:
        full = os.path.join(root, rel)
        profile.writable[rel] = os.access(full, os.W_OK) if os.path.exists(full) else os.access(os.path.dirname(full) or root, os.W_OK)
    profile.is_root_user = hasattr(os, "geteuid") and os.geteuid() == 0
    return profile


def discover_databases(root: str, files: List[str], environ: dict) -> List[DbTarget]:
    found: List[DbTarget] = []

    def add(target: Optional[DbTarget]) -> None:
        """Same connection seen twice (e.g. config with an unresolved password + complete env vars): merge,
        letting known values replace unknown ones, instead of keeping whichever came first."""
        if target is None:
            return
        for existing in found:
            if (existing.engine, existing.host, existing.port, existing.name, existing.user) == (
                target.engine, target.host, target.port, target.name, target.user
            ):
                if target.password and (not existing.password or "PASSWORD" in existing.source):
                    existing.password = target.password
                    existing.source = re.sub(r" \(unresolved: [^)]*\)", "", existing.source) + f" + password from {target.source}"
                if target.test_name and not existing.test_name:
                    existing.test_name = target.test_name
                return
        found.append(target)

    for rel in files:
        if not CONFIG_NAMES.search(rel):
            continue
        text = _read(os.path.join(root, rel))
        if rel.endswith(".py") and "DATABASES" in text:
            for target in _django_databases(text, rel, environ):
                add(target)
        for match in DSN.finditer(text):
            add(_parse_dsn(match.group(1), rel))

    for key in ("DATABASE_URL", "POSTGRES_URL", "PG_URL", "CLICKHOUSE_URL", "CLICKHOUSE_DSN"):
        if environ.get(key):
            add(_parse_dsn(environ[key], f"env {key}"))
    if environ.get("PGHOST") or environ.get("PGDATABASE"):
        add(DbTarget(
            "postgresql", environ.get("PGHOST", "localhost"), int(environ.get("PGPORT", "5432") or 5432),
            environ.get("PGUSER", ""), environ.get("PGPASSWORD", ""), environ.get("PGDATABASE", ""), source="env PG*",
        ))
    if environ.get("CLICKHOUSE_HOST"):
        add(DbTarget(
            "clickhouse", environ["CLICKHOUSE_HOST"], int(environ.get("CLICKHOUSE_PORT", "8123") or 8123),
            environ.get("CLICKHOUSE_USER", "default"), environ.get("CLICKHOUSE_PASSWORD", ""),
            environ.get("CLICKHOUSE_DB", environ.get("CLICKHOUSE_DATABASE", "default")), source="env CLICKHOUSE_*",
        ))
    # Complete connections first: a target with an unknown database or user is a poor default.
    found.sort(key=lambda t: (not t.name, not t.user, "unresolved" in t.source))
    return found


def _parse_dsn(dsn: str, source: str) -> Optional[DbTarget]:
    try:
        parsed = urlparse(dsn)
    except ValueError:
        return None
    scheme = parsed.scheme.split("+")[0]
    engine = "clickhouse" if scheme.startswith("clickhouse") else "postgresql"
    default_port = 8123 if engine == "clickhouse" else 5432
    try:
        port = parsed.port or default_port
    except ValueError:
        port = default_port
    return DbTarget(
        engine, parsed.hostname or "localhost", port, unquote(parsed.username or ""),
        unquote(parsed.password or ""), (parsed.path or "/").lstrip("/").split("?")[0], source=source,
    )


class _Unresolved:
    """A config value the static reader could not determine (it is never replaced by a guessed default)."""

    def __repr__(self) -> str:
        return "<unresolved>"


UNRESOLVED = _Unresolved()


def _env_lookup(node: ast.AST, environ: dict):
    """Resolve os.environ["X"], os.environ.get("X", d) and os.getenv("X", d); UNRESOLVED otherwise."""
    if isinstance(node, ast.Subscript):
        key = node.slice.value if isinstance(node.slice, ast.Constant) else getattr(getattr(node.slice, "value", None), "value", None)
        if ast.unparse(node.value) in ("os.environ", "environ") and isinstance(key, str):
            return environ.get(key, UNRESOLVED)
    if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
        name = ast.unparse(node.func)
        if name in ("os.environ.get", "os.getenv", "environ.get", "getenv"):
            default = _literal(node.args[1], environ) if len(node.args) > 1 else None
            return environ.get(node.args[0].value, default)
    return UNRESOLVED


def _literal(node: ast.AST, environ: Optional[dict] = None):
    """Literal values, plus environment lookups; anything else becomes UNRESOLVED."""
    environ = environ or {}
    if isinstance(node, ast.Dict):
        return {_literal(k, environ): _literal(v, environ) for k, v in zip(node.keys, node.values) if k is not None}
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_literal(e, environ) for e in node.elts]
    if isinstance(node, ast.Constant):
        return node.value
    return _env_lookup(node, environ)


def _text(value) -> str:
    return "" if value is None or value is UNRESOLVED else str(value)


def _django_databases(text: str, rel: str, environ: dict) -> List[DbTarget]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    targets: List[DbTarget] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DATABASES" for t in node.targets):
            value = _literal(node.value, environ)
            if not isinstance(value, dict):
                continue
            for alias, conf in value.items():
                if not isinstance(conf, dict):
                    continue
                engine_name = _text(conf.get("ENGINE"))
                engine = "clickhouse" if "clickhouse" in engine_name else "postgresql"
                if engine_name and "postgres" not in engine_name and "clickhouse" not in engine_name:
                    continue
                test = conf.get("TEST") if isinstance(conf.get("TEST"), dict) else {}
                name = _text(conf.get("NAME"))
                try:
                    port = int(_text(conf.get("PORT")) or (8123 if engine == "clickhouse" else 5432))
                except ValueError:
                    port = 5432
                unresolved = [k for k in ("NAME", "USER", "HOST", "PASSWORD") if conf.get(k) is UNRESOLVED]
                targets.append(DbTarget(
                    engine, _text(conf.get("HOST")) or "localhost", port, _text(conf.get("USER")),
                    _text(conf.get("PASSWORD")), name, _text(test.get("NAME")) or ("test_" + name if name else ""),
                    source=f"{rel} DATABASES[{alias!r}]" + (f" (unresolved: {', '.join(unresolved)})" if unresolved else ""),
                ))
    return targets


PACK_RULES = (
    ("postgresql", lambda p: "postgresql" in p.engines()),
    ("clickhouse", lambda p: "clickhouse" in p.engines() or any("clickhouse" in layer for layer in p.layers)),
    ("python", lambda p: "python" in p.languages),
    ("django", lambda p: "django" in p.layers),
    ("sqlalchemy", lambda p: "sqlalchemy" in p.layers),
    ("go", lambda p: "go" in p.languages),
    ("typescript", lambda p: "typescript" in p.languages or "javascript" in p.languages),
)


def select_packs(profile: EnvProfile, engine_hint: str = "unknown") -> List[str]:
    """Knowledge packs to inject: core always, the rest only when detected."""
    packs = ["core"]
    for name, rule in PACK_RULES:
        if rule(profile) or name == engine_hint:
            packs.append(name)
    return packs


# ======================================================================
# module: quarry.tools
# ======================================================================

"""Model-facing tools. Each tool is a small class; the registry turns them into schemas and dispatches calls."""


import base64
import difflib
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional


READ_MAX_LINES = 400
SEARCH_MAX_HITS = 50
CH_READ_PREFIXES = ("select", "with", "explain", "show", "describe", "desc", "exists")


class ToolContext:
    """Shared state for tools: repository root, scope policy, process runner, scratch dir, databases."""

    def __init__(
        self,
        root: str,
        spec: TaskSpec,
        runner: ProcessRunner,
        scratch_dir: str,
        databases: Optional[List[DbTarget]] = None,
        command_timeout=None,
    ):
        self.root = os.path.abspath(root)
        self.spec = spec
        self.runner = runner
        self.scratch_dir = scratch_dir
        self.databases = databases or []
        self.command_timeout = command_timeout or (lambda: 120.0)
        self.edited: List[str] = []
        self.finished = False
        self.summary = ""
        self.target_symbol = ""

    def resolve(self, path: str) -> Optional[str]:
        """Repo-relative path, or None when it escapes the repository."""
        full = os.path.abspath(os.path.join(self.root, path))
        if full != self.root and not full.startswith(self.root + os.sep):
            return None
        return os.path.relpath(full, self.root)

    @property
    def policy(self) -> ScopePolicy:
        return ScopePolicy(self.spec)

    def edit_refusal(self, rel: str, creating: bool = False) -> str:
        """Why an edit to (or creation of) `rel` is not allowed, or '' when it is."""
        refusal = self.policy.create_refusal(rel) if creating else self.policy.edit_refusal(rel)
        if refusal:
            return refusal
        if self.spec.scope.mode == "discover-one-symbol" and self.edited and rel not in self.edited:
            return f"the statement allows changing one method in one file; you already edited {self.edited[0]}"
        return ""


class Tool:
    name = ""
    description = ""
    parameters: Dict = {"type": "object", "properties": {}}

    def schema(self) -> Dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}

    def run(self, ctx: ToolContext, args: Dict) -> str:  # pragma: no cover - interface
        raise NotImplementedError


def _obj(props: Dict, required: List[str]) -> Dict:
    return {"type": "object", "properties": props, "required": required}


class ReadTool(Tool):
    name = "read"
    description = "Read a file by line range (1-based, inclusive, max 400 lines per call)."
    parameters = _obj(
        {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"]
    )

    def run(self, ctx, args):
        rel = ctx.resolve(str(args.get("path", "")))
        if rel is None:
            return "error: path is outside the repository"
        full = os.path.join(ctx.root, rel)
        if not os.path.isfile(full):
            return f"error: no such file {rel}"
        with open(full, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        start = max(1, int(args.get("start") or 1))
        end = int(args.get("end") or start + READ_MAX_LINES - 1)
        end = min(len(lines), end, start + READ_MAX_LINES - 1)
        body = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(start, end + 1))
        more = f"\n[... {len(lines) - end} more lines]" if end < len(lines) else ""
        return f"{rel} lines {start}-{end} of {len(lines)}\n{body}{more}"


class SearchTool(Tool):
    name = "search"
    description = "Search file contents with a regular expression. Returns the hit count and the first 50 hits."
    parameters = _obj({"pattern": {"type": "string"}, "path": {"type": "string", "description": "sub-directory or file"},
                       "glob": {"type": "string", "description": "e.g. *.py"}}, ["pattern"])

    def run(self, ctx, args):
        pattern = str(args.get("pattern", ""))
        rel = ctx.resolve(str(args.get("path") or "."))
        if rel is None:
            return "error: path is outside the repository"
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return f"error: bad pattern: {exc}"
        glob = str(args.get("glob") or "")
        glob_re = re.compile("^" + re.escape(glob).replace(r"\*", ".*").replace(r"\?", ".") + "$") if glob else None
        hits: List[str] = []
        total = 0
        base = os.path.join(ctx.root, rel)
        paths = [base] if os.path.isfile(base) else []
        if not paths:
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                paths.extend(os.path.join(dirpath, f) for f in sorted(filenames))
        for full in paths:
            name = os.path.basename(full)
            if glob_re and not glob_re.match(name):
                continue
            try:
                if os.path.getsize(full) > 2_000_000:
                    continue
                with open(full, encoding="utf-8", errors="strict") as handle:
                    for number, line in enumerate(handle, 1):
                        if regex.search(line):
                            total += 1
                            if len(hits) < SEARCH_MAX_HITS:
                                hits.append(f"{os.path.relpath(full, ctx.root)}:{number}: {line.rstrip()[:200]}")
            except (OSError, UnicodeDecodeError):
                continue
        return f"{total} hits" + ("\n" + "\n".join(hits) if hits else "")


class ListTool(Tool):
    name = "list"
    description = "List a directory (non-recursive), skipping vendored and cache directories."
    parameters = _obj({"path": {"type": "string"}}, [])

    def run(self, ctx, args):
        rel = ctx.resolve(str(args.get("path") or "."))
        if rel is None or not os.path.isdir(os.path.join(ctx.root, rel)):
            return "error: not a directory inside the repository"
        entries = sorted(os.listdir(os.path.join(ctx.root, rel)))
        shown = [e + ("/" if os.path.isdir(os.path.join(ctx.root, rel, e)) else "") for e in entries if e not in SKIP_DIRS]
        return "\n".join(shown[:300]) + (f"\n[... {len(shown) - 300} more]" if len(shown) > 300 else "")


class EditTool(Tool):
    name = "edit"
    description = (
        "Replace one exact occurrence of `old` with `new` in a file. `old` must match exactly once, "
        "including indentation. Edits outside the allowed scope are refused."
    )
    parameters = _obj({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, ["path", "old", "new"])

    def run(self, ctx, args):
        rel = ctx.resolve(str(args.get("path", "")))
        if rel is None:
            return "error: path is outside the repository"
        full = os.path.join(ctx.root, rel)
        if not os.path.isfile(full):
            return f"error: no such file {rel}"
        refusal = ctx.edit_refusal(rel)
        if refusal:
            return f"refused: {rel} is {refusal}" if refusal.startswith("outside") else f"refused: {refusal}"
        old, new = str(args.get("old", "")), str(args.get("new", ""))
        with open(full, encoding="utf-8", newline="") as handle:
            text = handle.read()
        crlf = "\r\n" in text
        if crlf:
            old, new = old.replace("\r\n", "\n").replace("\n", "\r\n"), new.replace("\r\n", "\n").replace("\n", "\r\n")
        count = text.count(old) if old else 0
        if count != 1:
            return f"error: `old` matched {count} times; it must match exactly once.\n" + _closest(text, old)
        with open(full, "w", encoding="utf-8", newline="") as handle:
            handle.write(text.replace(old, new, 1))
        if rel not in ctx.edited:
            ctx.edited.append(rel)
        return f"edited {rel}"


def _closest(text: str, old: str) -> str:
    lines = text.splitlines()
    first = (old.strip().splitlines() or [""])[0].strip()
    if not first:
        return ""
    ranked = sorted(
        ((difflib.SequenceMatcher(None, first, line.strip()).ratio(), i) for i, line in enumerate(lines)), reverse=True
    )[:1]
    if not ranked or ranked[0][0] < 0.5:
        return "No similar line found; re-read the file."
    i = ranked[0][1]
    window = "\n".join(f"{n + 1:>5}  {lines[n]}" for n in range(max(0, i - 3), min(len(lines), i + 4)))
    return "Closest text in the file:\n" + window


class CreateTool(Tool):
    name = "create"
    description = "Create a new file (only when the task calls for a new file, e.g. a migration)."
    parameters = _obj({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"])

    def run(self, ctx, args):
        rel = ctx.resolve(str(args.get("path", "")))
        if rel is None:
            return "error: path is outside the repository"
        full = os.path.join(ctx.root, rel)
        if os.path.exists(full):
            return "error: file exists; use edit"
        refusal = ctx.edit_refusal(rel, creating=True)
        if refusal:
            return f"refused: {refusal}"
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(str(args.get("content", "")))
        ctx.edited.append(rel)
        return f"created {rel}"


class ShellTool(Tool):
    name = "shell"
    description = (
        "Run a shell command in the repository root (tests, linters, scripts). Output is truncated. "
        "Put throw-away scripts in the scratch directory, never in the repository."
    )
    parameters = _obj({"command": {"type": "string"}, "timeout": {"type": "integer", "description": "seconds"}}, ["command"])

    def run(self, ctx, args):
        command = str(args.get("command", "")).strip()
        if not command:
            return "error: empty command"
        limit = ctx.command_timeout()
        timeout = min(float(args.get("timeout") or limit), limit)
        result = ctx.runner.run(command, timeout=timeout)
        return f"exit {result.code}\n{cap_output(result.output)}"


class ScratchTool(Tool):
    name = "scratch"
    description = "Write a throw-away file (script, SQL, data) into the scratch directory outside the repository; returns its path."
    parameters = _obj({"name": {"type": "string"}, "content": {"type": "string"}}, ["name", "content"])

    def run(self, ctx, args):
        name = os.path.basename(str(args.get("name") or "scratch.txt")) or "scratch.txt"
        os.makedirs(ctx.scratch_dir, exist_ok=True)
        path = os.path.join(ctx.scratch_dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(args.get("content", "")))
        return path


class SqlTool(Tool):
    name = "sql"
    description = (
        "Run SQL against the application's database. PostgreSQL runs inside a transaction that is rolled back "
        "(transaction-control statements are refused; sequences still advance). "
        "ClickHouse accepts read queries only (use inline values()/numbers() to build scenarios). "
        "`target`: index of the database (default 0) and optionally \"test\" to use its test database."
    )
    parameters = _obj({"query": {"type": "string"}, "target": {"type": "string"}}, ["query"])

    def run(self, ctx, args):
        if not ctx.databases:
            return "error: no database connection was found in the application config or environment"
        target = str(args.get("target") or "0")
        index = int(re.sub(r"\D", "", target) or 0)
        if index >= len(ctx.databases):
            return f"error: only {len(ctx.databases)} database(s) known"
        db = ctx.databases[index]
        name = db.test_name if "test" in target and db.test_name else db.name
        query = str(args.get("query", "")).strip().rstrip(";")
        refusal = transaction_control(query)
        if refusal:
            return f"refused: {refusal}; the tool manages the transaction itself"
        if db.engine == "clickhouse":
            return _clickhouse(db, name, query, ctx.command_timeout())
        return _postgres(ctx, db, name, query)


TX_CONTROL = re.compile(
    r"^\s*(commit|end|rollback|abort|begin|start\s+transaction|savepoint|release|prepare\s+transaction"
    r"|set\s+(session\s+)?characteristics|set\s+transaction)\b",
    re.IGNORECASE,
)


def sql_code_only(query: str) -> str:
    """Replace comments with spaces and literals/quoted identifiers with placeholders (PostgreSQL lexing:
    -- comments, nested /* */ comments, '...' with '' and E'...' escapes, "...", $tag$...$tag$)."""
    out: List[str] = []
    i, n = 0, len(query)
    while i < n:
        ch = query[i]
        if query.startswith("--", i):
            end = query.find("\n", i)
            i = n if end == -1 else end
            out.append(" ")
        elif query.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if query.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif query.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            out.append(" ")
        elif ch == "'" or (ch in "eE" and query.startswith("'", i + 1) and (i == 0 or not query[i - 1].isalnum())):
            escapes = ch in "eE"
            i += 2 if escapes else 1
            while i < n:
                if escapes and query[i] == "\\":
                    i += 2
                elif query[i] == "'" and query.startswith("''", i):
                    i += 2
                elif query[i] == "'":
                    i += 1
                    break
                else:
                    i += 1
            out.append("''")
        elif ch == '"':
            end = query.find('"', i + 1)
            i = n if end == -1 else end + 1
            out.append('"x"')
        elif ch == "$":
            match = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$", query[i:])
            if match:
                tag = match.group(0)
                end = query.find(tag, i + len(tag))
                i = n if end == -1 else end + len(tag)
                out.append("''")
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def transaction_control(query: str) -> str:
    """Name the first transaction-control statement or psql meta-command in `query`, or ''."""
    code = sql_code_only(query)
    for line in code.splitlines():
        if line.lstrip().startswith("\\"):
            return "psql meta-commands are not allowed"
    for statement in code.split(";"):
        match = TX_CONTROL.match(statement)
        if match:
            return f"`{match.group(1).upper()}` is not allowed"
    return ""


def _postgres(ctx: ToolContext, db: DbTarget, name: str, query: str) -> str:
    if not shutil.which("psql"):
        return "error: psql is not installed; run SQL through the application's own driver in a scratch script"
    script = f"SET statement_timeout = '30s';\nBEGIN;\n{query};\nROLLBACK;\n"
    env = {"PGPASSWORD": db.password, "PGCONNECT_TIMEOUT": "10"}
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-P", "pager=off", "-h", db.host, "-p", str(db.port or 5432),
           "-U", db.user or "postgres", "-d", name or "postgres"]
    result = ctx.runner.run(cmd, timeout=min(60.0, ctx.command_timeout()), env=env, stdin=script)
    return f"exit {result.code}\n{cap_output(result.output, 5000)}"


def _clickhouse(db: DbTarget, name: str, query: str, timeout: float) -> str:
    if not query.lower().lstrip("( \n").startswith(CH_READ_PREFIXES):
        return "refused: only read queries run against ClickHouse; build scenarios with inline values() or numbers()"
    params = urllib.parse.urlencode({"database": name or "default", "readonly": "2", "max_execution_time": "30"})
    url = f"http://{db.host}:{db.port or 8123}/?{params}"
    request = urllib.request.Request(url, data=(query + " FORMAT TSVWithNames").encode(), method="POST")
    token = base64.b64encode(f"{db.user or 'default'}:{db.password}".encode()).decode()
    request.add_header("Authorization", "Basic " + token)
    try:
        with urllib.request.urlopen(request, timeout=min(60.0, timeout)) as response:
            return cap_output(response.read().decode("utf-8", "replace"), 5000)
    except urllib.error.HTTPError as exc:
        return f"error {exc.code}: " + exc.read().decode("utf-8", "replace")[:2000]
    except (urllib.error.URLError, OSError) as exc:
        return f"error: {exc}"


class FinishTool(Tool):
    name = "finish"
    description = (
        "Call when the change is complete and you have verified it. Give a short summary and, if the task did not "
        "name it, the changed symbol as `symbol` (e.g. Class.method)."
    )
    parameters = _obj({"summary": {"type": "string"}, "symbol": {"type": "string"}}, ["summary"])

    def run(self, ctx, args):
        ctx.finished = True
        ctx.summary = str(args.get("summary", ""))[:2000]
        ctx.target_symbol = str(args.get("symbol") or "")
        return "ok"


class ToolRegistry:
    def __init__(self, tools: List[Tool]):
        self.tools = {tool.name: tool for tool in tools}

    def schemas(self) -> List[Dict]:
        return [tool.schema() for tool in self.tools.values()]

    def dispatch(self, ctx: ToolContext, name: str, args: Dict) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"error: unknown tool {name!r}; available: {', '.join(self.tools)}"
        try:
            return tool.run(ctx, args)
        except Exception as exc:  # a tool failure is feedback for the model, not a crash
            return f"error: {type(exc).__name__}: {exc}"


def default_tools() -> List[Tool]:
    return [ReadTool(), SearchTool(), ListTool(), EditTool(), CreateTool(), ShellTool(), ScratchTool(), SqlTool(), FinishTool()]


# ======================================================================
# module: quarry.loop
# ======================================================================

"""The tool-calling driver loop: bounded by turns, time, budget and stalls; keeps the transcript compact."""


from dataclasses import dataclass
from typing import Dict, List, Optional


NUDGE = "Continue with tool calls. When the change is complete and verified, call `finish`."
KEEP_RECENT = 8


@dataclass
class LoopOutcome:
    reason: str  # finished | deadline | budget | llm-error | stalled | max-turns
    turns: int
    detail: str = ""


class DriverLoop:
    def __init__(
        self,
        client,
        route: ModelRoute,
        registry: ToolRegistry,
        ctx: ToolContext,
        timer: PhaseTimer,
        max_turns: int = 40,
        compact_tokens: int = 40_000,
        pinned: int = 2,
        role: str = "driver",
    ):
        self.client = client
        self.route = route
        self.registry = registry
        self.ctx = ctx
        self.timer = timer
        self.max_turns = max_turns
        self.compact_tokens = compact_tokens
        self.pinned = pinned
        self.role = role

    def run(self, messages: List[Dict]) -> LoopOutcome:
        stalls = 0
        schemas = self.registry.schemas()
        for turn in range(1, self.max_turns + 1):
            if self.ctx.finished:
                return LoopOutcome("finished", turn - 1)
            if self.timer.expired():
                return LoopOutcome("deadline", turn - 1)
            self.compact(messages)
            try:
                reply = self.client.complete(
                    messages, self.route, tools=schemas, role=self.role, timeout=180.0, deadline=self.timer.end
                )
            except BudgetExhausted as exc:
                return LoopOutcome("budget", turn - 1, str(exc))
            except LLMError as exc:
                return LoopOutcome("llm-error", turn - 1, str(exc))
            messages.append(reply.message)
            if not reply.tool_calls:
                stalls += 1
                if stalls >= 3:
                    return LoopOutcome("stalled", turn)
                messages.append({"role": "user", "content": NUDGE})
                continue
            stalls = 0
            for call in reply.tool_calls:
                if self.timer.expired():
                    output = "skipped: the time for this phase is over"
                else:
                    output = call.error or self.registry.dispatch(self.ctx, call.name, call.arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            if self.timer.expired() and not self.ctx.finished:
                return LoopOutcome("deadline", turn)
            if self.ctx.finished:
                return LoopOutcome("finished", turn)
        return LoopOutcome("max-turns", self.max_turns)

    def compact(self, messages: List[Dict]) -> Optional[int]:
        """Shrink old tool outputs once the transcript is too large. Pinned messages are never touched."""
        if estimate_tokens(messages) <= self.compact_tokens:
            return None
        shrunk = 0
        for message in messages[self.pinned:-KEEP_RECENT]:
            if message.get("role") == "tool" and len(message.get("content") or "") > 200:
                first = (message["content"].splitlines() or [""])[0][:160]
                message["content"] = f"{first}\n[older output compacted]"
                shrunk += 1
        return shrunk


# ======================================================================
# module: quarry.telemetry
# ======================================================================

"""Versioned run telemetry: one JSON record per run (cost provenance, cache coverage, attempts), plus a readable line.

The JSON line is the contract with the bench runner. Missing values stay null; nothing is coerced to zero.
"""


import json
import re
from typing import Dict, List, Optional

TELEMETRY_PREFIX = "[quarry-telemetry] "
TELEMETRY_VERSION = 1
TELEMETRY_LINE = re.compile(r"\[quarry-telemetry\] (\{.*\})\s*$", re.M)


def _coverage(reported: int, total: int) -> str:
    if total == 0 or reported == 0:
        return "none"
    return "complete" if reported == total else "partial"


def cache_summary(records: List) -> Dict:
    """Read and write coverage, each with its own denominator (successful calls)."""
    ok = [r for r in records if r.ok]
    out: Dict = {"successful_calls": len(ok)}
    for key, field in (("read", "cached_tokens"), ("write", "cache_write_tokens")):
        reported = [getattr(r, field) for r in ok if getattr(r, field) is not None]
        out[key] = {
            "reported_calls": len(reported),
            "coverage": _coverage(len(reported), len(ok)),
            "tokens": sum(reported) if reported else None,
        }
    share_calls = [r for r in ok if r.cached_tokens is not None and r.prompt_tokens]
    prompt_total = sum(r.prompt_tokens for r in share_calls)
    out["read_share"] = {
        "value": round(sum(r.cached_tokens for r in share_calls) / prompt_total, 4) if prompt_total else None,
        "over_calls": len(share_calls),
        "coverage": _coverage(len(share_calls), len(ok)),
    }
    discounts = [r.cache_discount for r in ok if r.cache_discount is not None]
    out["reported_discount"] = {"sum": round(sum(discounts), 6) if discounts else None, "reported_calls": len(discounts)}
    return out


def call_rows(records: List) -> List[Dict]:
    rows = []
    for r in records:
        rows.append({
            "role": r.role, "model": r.model, "status": r.status, "ok": r.ok, "latency": round(r.latency, 2),
            "cost": None if r.cost is None else round(r.cost, 8), "cost_source": r.cost_source,
            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
            "cached_tokens": r.cached_tokens, "cache_write_tokens": r.cache_write_tokens,
            "cache_discount": r.cache_discount, "note": (r.note or "")[:120],
        })
    return rows


def build_record(records: List, wallet, extra: Optional[Dict] = None) -> Dict:
    record = {
        "version": TELEMETRY_VERSION,
        "attempts": len(records),
        "cost": wallet.summary(),
        "cache": cache_summary(records),
        "calls": call_rows(records),
    }
    record.update(extra or {})
    return record


def format_line(record: Dict) -> str:
    return TELEMETRY_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def human_summary(record: Dict) -> str:
    cost, cache = record["cost"], record["cache"]
    parts = [f"attempts={record['attempts']}", f"cost: provider ${cost['provider_usd']:.4f} + estimate ${cost['estimate_usd']:.4f}"]
    if cost["estimated_calls"]:
        parts.append(f"({cost['estimated_calls']} estimated call(s))")
    if cost["unknown_attempts"]:
        parts.append(f"+ {cost['unknown_attempts']} unknown-cost attempt(s), ${cost['unknown_reserved_usd']:.4f} reserved; total unknown")
    read, write, share = cache["read"], cache["write"], cache["read_share"]
    parts.append(
        f"cache read reported {read['reported_calls']}/{cache['successful_calls']} (tokens {read['tokens']}), "
        f"write reported {write['reported_calls']}/{cache['successful_calls']} (tokens {write['tokens']}), "
        f"read share {share['value']} over {share['over_calls']} call(s)"
    )
    return " ".join(parts)


def parse_log(text: str) -> Optional[Dict]:
    """The last telemetry record in a log, or None. An unknown version is returned flagged, never trusted."""
    matches = TELEMETRY_LINE.findall(text or "")
    if not matches:
        return None
    try:
        record = json.loads(matches[-1])
    except ValueError:
        return {"version": None, "unsupported": True, "reason": "unparseable telemetry line"}
    if record.get("version") != TELEMETRY_VERSION:
        return {"version": record.get("version"), "unsupported": True, "reason": "unsupported telemetry version"}
    return record


# ======================================================================
# module: quarry.shell
# ======================================================================

"""Control shell: settings, candidate store, and the workflow that ties the phases together."""


import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# USD per 1M tokens (input, output), checked on OpenRouter 2026-09-29. Actual cost comes from usage.cost when reported.
PRICES: Dict[str, Tuple[float, float]] = {
    "openai/gpt-5.6-luna": (0.20, 1.20),
    "xiaomi/mimo-v2.5": (0.14, 0.28),
    "tencent/hy3": (0.132, 0.528),
    "minimax/minimax-m2.5": (0.27, 1.08),
    "google/gemini-3.7-flash": (0.75, 3.75),
    "deepseek/deepseek-v4-pro-0813": (0.48, 4.20),
}
LINT_RUNNERS = ("ruff", "black", "flake8", "mypy", "pylint", "isort")


@dataclass
class Settings:
    driver: ModelRoute = field(default_factory=lambda: ModelRoute("openai/gpt-5.6-luna", "deepseek/deepseek-v4-pro-0813", 4096))
    driver_share: float = 0.80
    max_turns: int = 45
    fix_rounds: int = 2
    driver_budget_share: float = 0.85
    baseline_share: float = 0.35  # time allowed for the one baseline run of the statement's checks
    baseline_min_sec: float = 60.0
    check_factor: float = 3.0  # later check runs may take this multiple of the baseline duration
    check_min_sec: float = 120.0

    @classmethod
    def from_env(cls, environ: Optional[dict] = None) -> Settings:
        """Model choice can be overridden for local experiments; production uses the defaults."""
        env = os.environ if environ is None else environ
        settings = cls()
        if env.get("QUARRY_DRIVER_MODEL"):
            settings.driver = ModelRoute(env["QUARRY_DRIVER_MODEL"], env.get("QUARRY_FALLBACK_MODEL") or None, 4096)
        return settings


@dataclass
class Candidate:
    diff: str
    evidence: float
    eligible: bool  # guard passed and no required check failed
    notes: List[str] = field(default_factory=list)
    checks_passed: Optional[bool] = None  # None: the statement had no checks
    problems: List[str] = field(default_factory=list)


class CandidateStore:
    def __init__(self):
        self.items: List[Candidate] = []

    def add(self, candidate: Candidate) -> None:
        if candidate.diff.strip():
            self.items.append(candidate)

    def ranked(self) -> List[Candidate]:
        return sorted(self.items, key=lambda c: (c.eligible, c.evidence, -len(c.diff)), reverse=True)

    def best(self) -> Optional[Candidate]:
        ranked = self.ranked()
        return ranked[0] if ranked else None


def expand_templates(spec: TaskSpec, changed: List[str]) -> List[str]:
    commands = list(spec.checks)
    for template in spec.check_templates:
        runner = template.split(" ", 1)[0]
        files = [p for p in changed if p.endswith(".py")] if runner in LINT_RUNNERS else changed
        if files:
            commands.append(template.replace("{changed_files}", " ".join(files)))
    return commands


class Workflow:
    """One run: compile the spec, profile, drive the model, gate, keep the best candidate."""

    def __init__(self, statement: str, root: str, environ: Optional[dict] = None, client=None, settings: Optional[Settings] = None):
        env = os.environ if environ is None else environ
        self.statement = statement
        self.root = os.path.abspath(root)
        self.clock = Clock.from_env(env)
        self.wallet = Wallet.from_env(env, PRICES)
        self.runner = ProcessRunner(self.root)
        self.repo = GitRepo(self.root, self.runner)
        self.client = client or ProxyClient(self.wallet, env)
        self.settings = settings or Settings.from_env(env)
        self.store = CandidateStore()
        self.guard = Guard()
        self.scratch = tempfile.mkdtemp(prefix="quarry-")
        self.log: List[str] = []
        self.spec: Optional[TaskSpec] = None
        self.profile: Optional[EnvProfile] = None
        self.baseline: Dict[str, Dict] = {}  # command -> baseline observation (H-SHELL-11)
        self.check_log: List[Dict] = []  # every check run, for the run log and telemetry (H-SHELL-13)
        self.rounds: List[Dict] = []
        self.final: Dict = {}

    def note(self, text: str) -> None:
        self.log.append(text)
        print(f"[quarry] {text}", file=sys.stderr, flush=True)

    # ------------------------------------------------------------ phases

    def prepare(self) -> None:
        self.repo.ensure_baseline()
        self.spec = compile_statement(self.statement, self.root)
        self.profile = build_profile(self.root, self.spec.scope.files)
        self.note(f"spec kind={self.spec.kind} scope={self.spec.scope.mode} files={self.spec.scope.files} symbols={self.spec.scope.symbols}")

    def messages(self) -> List[Dict]:
        spec, profile = self.spec, self.profile
        packs = select_packs(profile, spec.engine)
        system = asset("prompts/driver.md").strip() + "\n\n" + pack_text(packs)
        user = "\n\n".join([
            "## Task checklist\n" + spec.render(),
            "## Environment\n" + profile.render() + f"\nScratch directory (outside the repository): {self.scratch}"
            + self.baseline_summary(),
            asset(f"prompts/kind_{spec.kind}.md").strip(),
            "## Task statement\n" + spec.statement.strip(),
        ])
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def run_command(self, command: str, timeout: float, round_label: str) -> Dict:
        started = self.clock.now()
        result = self.runner.run("set -e\n" + command, timeout=max(5.0, timeout))
        lines = [line for line in result.output.strip().splitlines() if line.strip()]
        obs = {
            "round": round_label, "command": command.splitlines()[0][:100], "exit": result.code,
            "seconds": round(self.clock.now() - started, 1), "timed_out": result.timed_out,
            "tail": " | ".join(lines[-3:])[:300], "output": result.output,
        }
        self.note(f"check [{round_label}] `{obs['command']}` exit {obs['exit']} in {obs['seconds']}s"
                  + (" (timed out)" if obs["timed_out"] else "") + (f": {obs['tail'][:160]}" if result.code else ""))
        self.check_log.append({k: v for k, v in obs.items() if k != "output"})
        return obs

    def baseline_checks(self) -> None:
        """Run the statement's checks once before any edit: learn their duration, warm caches, and see whether
        they pass on unmodified code (H-SHELL-11)."""
        commands = expand_templates(self.spec, [])
        for command in commands:
            budget = min(self.settings.baseline_share * self.clock.total, self.clock.remaining() - 60)
            obs = self.run_command(command, max(self.settings.baseline_min_sec, budget), "baseline")
            self.baseline[command] = {"seconds": obs["seconds"], "ok": obs["exit"] == 0 and not obs["timed_out"],
                                      "timed_out": obs["timed_out"]}
        if commands and self.repo.changed().all_paths():
            undone = self.repo.undo_run_changes()
            self.note(f"baseline checks changed {len(undone)} path(s); restored them before editing")

    def baseline_summary(self) -> str:
        """What the baseline run of the statement's checks showed, for the model's planning."""
        if not self.baseline:
            return ""
        lines = ["", "The task's checks were run once on the unmodified code:"]
        for command, base in self.baseline.items():
            if base["timed_out"]:
                state = (f"did not finish within {base['seconds']:.0f}s; it is too slow to run repeatedly here, "
                         "so do not run it yourself; verify with narrower tests or scripts instead")
            elif base["ok"]:
                state = f"passed in {base['seconds']:.0f}s"
            else:
                state = f"already fails before any change (after {base['seconds']:.0f}s)"
            lines.append(f"- `{command.splitlines()[0][:100]}`: {state}")
        return "\n".join(lines)

    def gate(self, ctx: ToolContext, round_label: str = "") -> Tuple[GuardReport, List[str], Optional[bool]]:
        """Guard, then the statement's checks. Evidence belongs to the exact tree it was produced on:
        if the checks change the source, the guard and the checks run again on the new tree."""
        target = None
        if ctx.target_symbol and len(ctx.edited) == 1:
            target = (ctx.edited[0], ctx.target_symbol)
        report = self.guard.run(GuardContext(self.repo, self.spec, target))
        before = self.repo.fingerprint()
        checks, failures = self.run_checks(round_label)
        if checks is not None and self.repo.fingerprint() != before:
            self.note("the checks changed the source or created source files; re-running guard and checks")
            report = self.guard.run(GuardContext(self.repo, self.spec, target))
            before = self.repo.fingerprint()
            checks, failures = self.run_checks(round_label + "-rerun")
            if self.repo.fingerprint() != before:
                checks = False
                failures.append("the checks keep modifying or creating source files, so no stable tree was validated")
                self.guard.run(GuardContext(self.repo, self.spec, target))
        return report, failures, checks

    def run_checks(self, round_label: str = "") -> Tuple[Optional[bool], List[str]]:
        """Run the statement's checks (H-SHELL-12). True: all ran and passed. False: a check failed that passed
        on unmodified code. None: no checks, or no usable evidence (skipped, too slow, or failing before any change)."""
        changed = self.repo.changed()
        commands = expand_templates(self.spec, changed.modified + changed.added)
        if not commands:
            return None, []
        failures: List[str] = []
        unknown = False
        for command in commands:
            base = self.baseline.get(command)
            if base and base["timed_out"]:
                unknown = True
                self.check_log.append({"round": round_label, "command": command.splitlines()[0][:100],
                                       "skipped": "baseline run exceeded its time budget"})
                continue
            if self.clock.remaining() < 30:
                failures.append(f"not run (no time): {command}")
                break
            if base:
                timeout = min(max(self.settings.check_min_sec, self.settings.check_factor * base["seconds"]),
                              self.clock.remaining())
            else:
                timeout = min(self.clock.command_timeout(600), self.clock.remaining())
            obs = self.run_command(command, timeout, round_label)
            if obs["exit"] == 0 and not obs["timed_out"]:
                continue
            if base and not base["ok"]:
                unknown = True  # it failed on unmodified code too: not evidence against the patch
                continue
            failures.append(f"`{command}` exited {obs['exit']}"
                            + (" (timed out)" if obs["timed_out"] else "") + f":\n{cap_output(obs['output'], 2500)}")
        if failures:
            return False, failures
        return (None if unknown else True), []

    def evidence_of(self, report: GuardReport, checks: Optional[bool], outcome: LoopOutcome) -> float:
        soft = sum(1 for r in report.results if not r.ok and not r.hard)
        return 3.0 * (checks is True) + 1.0 * (outcome.reason == "finished") - 0.5 * soft

    def run(self) -> str:
        self.prepare()
        self.baseline_checks()
        messages = self.messages()
        registry = ToolRegistry(default_tools())
        timer = self.clock.slice(self.settings.driver_share)
        ctx = ToolContext(
            self.root, self.spec, self.runner, self.scratch, self.profile.databases,
            command_timeout=lambda: max(5.0, min(self.clock.command_timeout(300), timer.remaining())),
        )
        with self.wallet.phase("driver", self.wallet.spendable * self.settings.driver_budget_share):
            for round_no in range(self.settings.fix_rounds + 1):
                loop = DriverLoop(self.client, self.settings.driver, registry, ctx, timer, self.settings.max_turns)
                outcome = loop.run(messages)
                self.note(f"round {round_no}: {outcome.reason} after {outcome.turns} turns; consumed ${self.wallet.consumed_usd:.4f}")
                report, failures, checks = self.gate(ctx, f"r{round_no}")
                self.rounds.append({
                    "round": round_no, "loop": outcome.reason, "turns": outcome.turns, "guard_eligible": report.eligible,
                    "guard_failed": [r.name for r in report.failures() if r.hard], "checks": checks,
                })
                problems = [f"{r.name}: {r.detail}" for r in report.failures() if r.hard] + failures
                self.store.add(Candidate(
                    report.diff, self.evidence_of(report, checks, outcome), report.eligible and checks is not False,
                    report.repairs, checks, problems,
                ))
                problems += [f"{r.name}: {r.detail}" for r in report.failures() if not r.hard]
                if report.eligible and checks is not False:
                    break
                if outcome.reason in ("budget", "deadline", "llm-error") or timer.expired() or self.wallet.spent:
                    break
                ctx.finished = False
                feedback = asset("prompts/checks_failed.md").strip()
                if report.repairs:
                    feedback += "\nAutomatic corrections applied to the working tree: " + "; ".join(report.repairs)
                messages.append({"role": "user", "content": feedback + "\n\n" + "\n\n".join(problems)[:6000]})
        return self.result()

    def result(self) -> str:
        best = self.store.best()
        if best is not None:
            self.final = {"source": "candidate", "eligible": best.eligible, "checks_passed": best.checks_passed,
                          "evidence": best.evidence, "problems": [p.splitlines()[0][:160] for p in best.problems]}
            if best.eligible:
                self.note(f"returning candidate; evidence={best.evidence}")
            else:
                reasons = "; ".join(p.splitlines()[0][:160] for p in best.problems) or "unknown"
                self.note(f"returning last-resort candidate; evidence={best.evidence}; failed: {reasons}")
            return best.diff
        return self.fallback_diff()

    def fallback_diff(self) -> str:
        """Last resort: whatever the guarded working tree holds, if it at least applies."""
        if self.spec is None:
            return ""
        try:
            report = self.guard.run(GuardContext(self.repo, self.spec))
            if report.diff.strip() and self.repo.apply_check(report.diff).ok:
                self.final = {"source": "working-tree fallback", "eligible": report.eligible, "checks_passed": None}
                self.note(f"returning last-resort working-tree diff (eligible={report.eligible})")
                return report.diff
            return ""
        except Exception as exc:  # the fallback must never raise
            self.note(f"fallback failed: {exc}")
            return ""

    def handoff(self, diff: str) -> str:
        """Leave the repository as it was at start, then return the first patch (chosen one, then the other
        candidates by rank) that passes the platform's own check: `git apply --check` on that tree."""
        if not self.repo.head:
            return diff
        undone = self.repo.undo_run_changes()
        if undone:
            self.note(f"restored {len(undone)} path(s) to the start state before returning")
        options = [diff] + [c.diff for c in self.store.ranked() if c.diff != diff]
        for index, option in enumerate(options):
            if not option.strip():
                continue
            check = self.repo.apply_check_worktree(option)
            if check.ok:
                if index:
                    self.note(f"chosen patch did not apply; returning candidate #{index} instead")
                self.final["returned_option"] = index
                return option
            self.note(f"patch #{index} does not apply to the restored tree: {check.output.strip()[:200]}")
        return ""

    def telemetry(self) -> str:
        """Emit the versioned JSON record (the bench runner's contract) and return the readable summary."""
        record = build_record(
            getattr(self.client, "telemetry", []), self.wallet,
            {"elapsed_sec": round(self.clock.elapsed(), 1), "cap_usd": self.wallet.cap,
             "baseline_checks": [dict(command=c.splitlines()[0][:100], **v) for c, v in self.baseline.items()],
             "checks": self.check_log, "rounds": self.rounds, "final": self.final},
        )
        print(format_line(record), file=sys.stderr, flush=True)
        return human_summary(record)


def run_agent(statement: str, root: str, environ: Optional[dict] = None, client=None, settings: Optional[Settings] = None) -> str:
    workflow = Workflow(statement, root, environ, client, settings)
    diff = ""
    try:
        diff = workflow.run()
    except BudgetExhausted as exc:
        workflow.note(f"budget exhausted: {exc}")
        diff = workflow.result()
    except Exception as exc:
        workflow.note(f"workflow error: {type(exc).__name__}: {exc}")
        diff = workflow.result()
    finally:
        workflow.runner.kill_all()
    diff = safe_handoff(workflow, diff)
    workflow.note(workflow.telemetry())
    return diff


def safe_handoff(workflow: Workflow, diff: str) -> str:
    """Hand-off with a retry. If cleanup keeps failing, a patch is returned only if it applies to the tree as it
    actually is now (the platform's next step); otherwise nothing is returned."""
    for attempt in (1, 2):
        try:
            return workflow.handoff(diff)
        except Exception as exc:
            workflow.note(f"hand-off error (attempt {attempt}): {type(exc).__name__}: {exc}")
    try:
        if diff.strip() and workflow.repo.apply_check_worktree(diff).ok:
            return diff
    except Exception as exc:
        workflow.note(f"final apply-check error: {type(exc).__name__}: {exc}")
    workflow.note("no patch returned: the working tree could not be restored and the patch does not apply to it")
    return ""


# ======================================================================
# module: quarry.agent
# ======================================================================

"""Entry point: agent_main(input) -> unified diff of the change made in the current repository."""


import os



def agent_main(input: dict) -> str:
    statement = str((input or {}).get("problem_statement") or "")
    diff = run_agent(statement, os.getcwd())
    if not diff.strip():
        raise RuntimeError("no change was produced")
    return diff
