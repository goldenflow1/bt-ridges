"""Problem statement → TaskSpec, deterministically (regex + markdown structure)."""

from __future__ import annotations

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
