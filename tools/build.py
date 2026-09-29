#!/usr/bin/env python3
"""Bundle src/quarry into one readable file: dist/agent.py (H-BUILD-01..03).

Modules are concatenated in dependency order; intra-package imports are removed; prompt and pack
text is embedded as EMBEDDED_ASSETS. The build fails on duplicate top-level names, on non-stdlib
imports and on syntax beyond Python 3.9.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import sys
from typing import Dict, List, Set, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "src", "quarry")
ENTRY = "agent"
HEADER = '''"""Quarry: an agent that changes how an application fetches data from PostgreSQL or ClickHouse.

Single-file build of the quarry package (see src/quarry/ in the project for the module sources).
Entry point: agent_main({"problem_statement": ...}) -> unified diff.
"""

from __future__ import annotations

import sys
import types

# Loaders may execute this file without registering it in sys.modules; dataclasses (Python < 3.12)
# looks the defining module up there, so make sure an entry exists.
sys.modules.setdefault(__name__, types.ModuleType(__name__))
'''


class BuildError(Exception):
    pass


def module_sources(pkg: str = PKG) -> Dict[str, str]:
    out = {}
    for name in sorted(os.listdir(pkg)):
        if name.endswith(".py") and name != "__init__.py":
            with open(os.path.join(pkg, name), encoding="utf-8") as handle:
                out[name[:-3]] = handle.read()
    return out


def internal_imports(tree: ast.Module) -> List[Tuple[str, int, int]]:
    """(module, first line, last line) of every `quarry` import; other forms are rejected."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (node.module == "quarry" or node.module.startswith("quarry.")):
            if node.module == "quarry" or node.col_offset != 0:
                raise BuildError(f"line {node.lineno}: only top-level `from quarry.<module> import ...` is allowed")
            found.append((node.module.split(".", 1)[1], node.lineno, node.end_lineno))
        elif isinstance(node, ast.Import) and any(a.name == "quarry" or a.name.startswith("quarry.") for a in node.names):
            raise BuildError(f"line {node.lineno}: `import quarry...` is not allowed; use `from quarry.<module> import ...`")
    return found


def external_imports(tree: ast.Module) -> Set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    names.discard("quarry")
    names.discard("__future__")
    return names


def top_level_names(tree: ast.Module) -> Set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
    return names


def dependency_order(deps: Dict[str, Set[str]], entry: str = ENTRY) -> List[str]:
    order: List[str] = []
    state: Dict[str, int] = {}

    def visit(name: str, chain: List[str]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            raise BuildError("import cycle: " + " -> ".join(chain + [name]))
        if name not in deps:
            raise BuildError(f"unknown module quarry.{name}")
        state[name] = 1
        for dep in sorted(deps[name]):
            visit(dep, chain + [name])
        state[name] = 2
        order.append(name)

    visit(entry, [])
    return order


def strip_lines(source: str, spans: List[Tuple[int, int]]) -> str:
    lines = source.splitlines(keepends=True)
    drop = set()
    for first, last in spans:
        drop.update(range(first, last + 1))
    for i, line in enumerate(lines, 1):
        if line.strip() == "from __future__ import annotations":
            drop.add(i)
    return "".join(line for i, line in enumerate(lines, 1) if i not in drop)


def embed_assets(pkg: str = PKG) -> str:
    entries = []
    for folder in ("prompts", "packs"):
        base = os.path.join(pkg, folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith(".md"):
                with open(os.path.join(base, name), encoding="utf-8") as handle:
                    text = handle.read()
                body = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
                entries.append(f'    "{folder}/{name}": """\\\n{body}""",\n')
    return "EMBEDDED_ASSETS = {\n" + "".join(entries) + "}\n"


def build(pkg: str = PKG) -> str:
    sources = module_sources(pkg)
    trees, deps = {}, {}
    for name, source in sources.items():
        tree = ast.parse(source, filename=f"{name}.py")
        trees[name] = tree
        deps[name] = {mod for mod, _a, _b in internal_imports(tree)}
    order = dependency_order(deps)

    stdlib = set(getattr(sys, "stdlib_module_names", ())) or None
    owners: Dict[str, str] = {}
    for name in order:
        if stdlib is not None:
            foreign = sorted(external_imports(trees[name]) - stdlib)
            if foreign:
                raise BuildError(f"quarry.{name} imports non-stdlib modules: {foreign}")
        for top in top_level_names(trees[name]):
            if top in owners and not top.startswith("__"):
                raise BuildError(f"duplicate top-level name {top!r} in quarry.{owners[top]} and quarry.{name}")
            owners[top] = name

    parts = [HEADER, "\n", embed_assets(pkg)]
    for name in order:
        spans = [(a, b) for _m, a, b in internal_imports(trees[name])]
        body = strip_lines(sources[name], spans).strip("\n")
        parts.append(f"\n\n# {'=' * 70}\n# module: quarry.{name}\n# {'=' * 70}\n\n{body}\n")
    bundle = "".join(parts)
    ast.parse(bundle, feature_version=(3, 9))
    compile(bundle, "agent.py", "exec")
    if "def agent_main(" not in bundle:
        raise BuildError("bundle does not define agent_main")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=os.path.join(ROOT, "dist", "agent.py"))
    args = parser.parse_args()
    try:
        bundle = build()
    except (BuildError, SyntaxError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(bundle)
    digest = hashlib.sha256(bundle.encode()).hexdigest()[:16]
    print(f"wrote {args.out}: {len(bundle.splitlines())} lines, {len(bundle)} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
