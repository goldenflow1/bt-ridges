"""Deterministic patch hygiene: repairs that bring the tree back into scope, then checks that gate a candidate."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from quarry.git import ChangeSet, GitRepo
from quarry.pysource import (
    changed_functions,
    find_symbol,
    find_symbol_anywhere,
    header_equal,
    module_imports,
    module_rule_delta,
    outside_identical,
    parse_or_none,
    rule_violations,
    splice,
    unbound_names,
)
from quarry.scope import ScopePolicy
from quarry.spec import TaskSpec


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
