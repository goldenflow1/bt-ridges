"""Model-facing tools. Each tool is a small class; the registry turns them into schemas and dispatches calls."""

from __future__ import annotations

import base64
import difflib
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from quarry.proc import ProcessRunner, cap_output
from quarry.profile import SKIP_DIRS, DbTarget
from quarry.scope import ScopePolicy
from quarry.spec import TaskSpec

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
