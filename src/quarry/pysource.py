"""Python source surgery: locate a symbol, splice it byte-exactly, and check its header, imports and constructs."""

from __future__ import annotations

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
