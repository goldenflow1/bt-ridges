"""Repository and environment profiling: languages, query layers, databases, tools. No LLM, no app imports."""

from __future__ import annotations

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
