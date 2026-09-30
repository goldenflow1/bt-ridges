"""Control shell: settings, candidate store, and the workflow that ties the phases together."""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from quarry.assets import asset, pack_text
from quarry.clock import Clock
from quarry.git import GitRepo
from quarry.guard import Guard, GuardContext, GuardReport
from quarry.llm import ModelRoute, ProxyClient
from quarry.loop import DriverLoop, LoopOutcome
from quarry.proc import ProcessRunner, cap_output
from quarry.profile import EnvProfile, build_profile, select_packs
from quarry.spec import TaskSpec, compile_statement
from quarry.telemetry import build_record, format_line, human_summary
from quarry.tools import ToolContext, ToolRegistry, default_tools
from quarry.wallet import BudgetExhausted, Wallet

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
        self.still_failing: List[str] = []  # statement checks failing before the change and after it (H-SHELL-14)
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
                                      "timed_out": obs["timed_out"], "tail": obs["tail"]}
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
        self.still_failing = []
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
                self.still_failing.append(
                    f"`{command}` failed before any change ({base['tail'][:300] or 'no output'}) and still fails "
                    f"after your change (exit {obs['exit']}):\n{cap_output(obs['output'], 2500)}")
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
                still = report.eligible and checks is None and self.still_failing
                if report.eligible and checks is not False and not still:
                    break
                if outcome.reason in ("budget", "deadline", "llm-error") or timer.expired() or self.wallet.spent:
                    break
                ctx.finished = False
                if still:
                    self.note(f"round {round_no}: {len(self.still_failing)} check(s) failing before the change still fail")
                    messages.append({"role": "user", "content": asset("prompts/checks_still_failing.md").strip()
                                     + "\n\n" + "\n\n".join(self.still_failing)[:6000]})
                    continue
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
