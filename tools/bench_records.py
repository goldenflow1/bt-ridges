"""Trial provenance and observations for the live bench (B-RUN-02, B-RUN-04).

Observations are recorded before any diagnosis. The automatic label follows a fixed precedence and never overrides
the underlying observations; manual diagnoses are separate annotations.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import stat
import subprocess
from typing import Callable, Dict, List, Optional

DIGEST_VERSION = "task-tree-v1"
# Excluded from the task digest (documented, B-RUN-04): VCS metadata and disposable caches only.
DIGEST_EXCLUDE = re.compile(r"(^|/)(\.git|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache)(/|$)|\.pyc$")

# Harbor / Ridges failure types by responsibility (B-RUN-02).
VOID_INFRASTRUCTURE = {"EnvironmentStartTimeoutError", "HealthcheckError", "SandboxBuildFailedError",
                       "AgentSetupTimeoutError"}
AGENT_MECHANICAL = {"MinerRuntimeError", "MinerInvalidPatchError", "MinerPatchApplyError", "AgentTimeoutError",
                    "NonZeroAgentExitCodeError"}
CHECKER_UNRESOLVED = {"VerifierTimeoutError", "RewardFileNotFoundError", "RewardFileEmptyError",
                      "VerifierOutputParseError", "DownloadVerifierDirError"}
GUARD_CHECK_NAMES = ("scope", "file-modes", "python-compiles", "bounded-symbol", "signature", "imports",
                     "statement-rules", "non-empty", "apply-check")
MAX_SETUP_REPLACEMENTS = 2


def task_digest(task_dir: str) -> str:
    """Canonical digest of every task input: sorted entries of (relative path, type, mode, content or link target).
    Directories are included; symlinks are recorded by target and never followed."""
    digest = hashlib.sha256(DIGEST_VERSION.encode() + b"\0")
    entries = []
    for dirpath, dirnames, filenames in os.walk(task_dir, followlinks=False):
        rel_dir = os.path.relpath(dirpath, task_dir)
        for name in dirnames + filenames:
            rel = os.path.normpath(os.path.join(rel_dir, name))
            if not DIGEST_EXCLUDE.search(rel):
                entries.append(rel)
        dirnames[:] = [d for d in dirnames if not DIGEST_EXCLUDE.search(os.path.normpath(os.path.join(rel_dir, d)))]
    for rel in sorted(entries):
        full = os.path.join(task_dir, rel)
        info = os.lstat(full)
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            kind, payload = "link", os.readlink(full).encode()
        elif stat.S_ISDIR(info.st_mode):
            kind, payload = "dir", b""
        else:
            kind = "file"
            with open(full, "rb") as handle:
                payload = hashlib.sha256(handle.read()).hexdigest().encode()
        record = json.dumps([rel, kind, oct(mode)]).encode()
        digest.update(len(record).to_bytes(4, "big") + record + len(payload).to_bytes(4, "big") + payload)
    return f"{DIGEST_VERSION}:{digest.hexdigest()}"


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def observe(trial_dir: str, cli_output: str, telemetry: Optional[Dict]) -> Dict:
    """Facts about one trial, each from its own source; nothing is inferred here."""
    obs: Dict = {"trial_dir": trial_dir or None}
    result = {}
    if trial_dir:
        try:
            result = json.loads(_read(os.path.join(trial_dir, "result.json")) or "{}")
        except ValueError:
            result = {}
    exc = (result.get("exception_info") or {}) if isinstance(result, dict) else {}
    obs["exception_type"] = exc.get("exception_type")
    obs["exception_message"] = (exc.get("exception_message") or "")[:300] or None
    reward_match = re.search(r"^reward:\s*([\d.]+)", cli_output or "", re.M)
    reward_file = _read(os.path.join(trial_dir, "verifier", "reward.txt")).strip() if trial_dir else ""
    obs["reward"] = float(reward_match.group(1)) if reward_match else None
    obs["reward_file"] = reward_file or None
    obs["checker_completed"] = obs["reward"] is not None and obs["exception_type"] is None
    patch = _read(os.path.join(trial_dir, "agent", "patch.diff")) if trial_dir else ""
    obs["patch_sha256"] = hashlib.sha256(patch.encode()).hexdigest()[:16] if patch.strip() else None
    apply_log = _read(os.path.join(trial_dir, "agent", "git-apply-check.log")) if trial_dir else ""
    code = re.search(r"\[return_code\]\s*(\d+)", apply_log)
    obs["apply_check_ok"] = (int(code.group(1)) == 0) if code else None
    final = (telemetry or {}).get("final") or {}
    rounds = (telemetry or {}).get("rounds") or []
    obs["telemetry"] = bool(telemetry) and not (telemetry or {}).get("unsupported")
    obs["final_source"] = final.get("source")
    obs["final_eligible"] = final.get("eligible")
    obs["final_checks_passed"] = final.get("checks_passed")
    obs["final_problems"] = final.get("problems") or []
    obs["termination"] = rounds[-1].get("loop") if rounds else None
    cost = (telemetry or {}).get("cost") or {}
    obs["accounting_complete"] = cost.get("accounting_complete")
    return obs


TASK_ENVIRONMENT_DEFECT = re.compile(r"Unsupported task environment|Failed to install local miner baseline packages")


def validity(obs: Dict) -> str:
    """valid | void-infrastructure | task-environment | unresolved, by responsibility (not timing).
    A broken task image is neither the agent's fault nor transient: fix and re-validate the task, don't retry."""
    if TASK_ENVIRONMENT_DEFECT.search(obs.get("exception_message") or ""):
        return "task-environment"
    kind = obs.get("exception_type")
    if kind in VOID_INFRASTRUCTURE:
        return "void-infrastructure"
    if kind in CHECKER_UNRESOLVED:
        return "unresolved"
    if kind and kind not in AGENT_MECHANICAL:
        return "unresolved"
    return "valid"


def auto_label(obs: Dict) -> str:
    """Fixed precedence (plan M0.5 W5). Observations are kept alongside; this never overrides them."""
    kind = obs.get("exception_type")
    reward = obs.get("reward")
    if reward is not None and kind in AGENT_MECHANICAL:
        return "unknown"  # contradictory authoritative outcomes
    state = validity(obs)
    if state == "void-infrastructure":
        return "infrastructure-void"
    if state == "task-environment":
        return "task-environment-defect"
    if state == "unresolved":
        return "unknown"
    if kind in AGENT_MECHANICAL:
        no_candidate = not obs.get("patch_sha256") and not obs.get("final_source")
        if kind == "MinerRuntimeError" and no_candidate and obs.get("termination") in ("budget", "deadline"):
            return obs["termination"]  # a voluntary no-patch result, not a transport failure
        return "mechanical"
    if reward is None:
        return "unknown"
    if reward >= 1:
        return "solved"
    problems = obs.get("final_problems") or []
    if obs.get("final_eligible") is False and problems:
        if any(p.split(":", 1)[0].strip() in GUARD_CHECK_NAMES for p in problems):
            return "guard-failed"
        return "checks-failed"
    return "unsolved"


def cli_version(ridges_root: str) -> Optional[str]:
    head = os.path.join(ridges_root, ".git", "HEAD")
    ref = _read(head).strip()
    if ref.startswith("ref: "):
        return _read(os.path.join(ridges_root, ".git", ref[5:])).strip()[:12] or None
    return ref[:12] or None


def expected_tasks(root: str, task_set: str) -> List[str]:
    return sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join(root, "bench", "tasks", task_set, "*", "task.toml")))


# ---------------------------------------------------------------------------------- runtime identity (B-RUN-01)


def _run(cmd: List[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def host_identity(ridges_root: str, run: Callable[[List[str]], str] = _run) -> Dict:
    """What the run executed on. Unknown values are recorded as None, never guessed."""
    cpu = ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            cpu = next((line.split(":", 1)[1].strip() for line in handle if line.startswith("model name")), "")
    except OSError:
        pass
    harbor = run([os.path.join(ridges_root, ".venv", "bin", "python"), "-c",
                  "import importlib.metadata as m; print(m.version('harbor'))"])
    return {
        "cpu": cpu or None,
        "cpus": os.cpu_count(),
        "docker": run(["docker", "version", "--format", "{{.Server.Version}}"]) or None,
        "harbor": harbor or None,
        "ridges_cli_commit": cli_version(ridges_root),
    }


def trial_images(trial_dir: str, run: Callable[[List[str]], str] = _run) -> Dict[str, Optional[str]]:
    """Image IDs of the containers Harbor built for this trial (named after the trial)."""
    if not trial_dir:
        return {}
    prefix = os.path.basename(os.path.normpath(trial_dir)).lower() + "__"
    listing = run(["docker", "images", "--no-trunc", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"])
    images = {}
    for line in listing.splitlines():
        name, _, image_id = line.partition(" ")
        if name.startswith(prefix):
            images[name[len(prefix):]] = image_id or None
    return images


def inputs_unchanged(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
    """Names of inputs (task digests, bundle hash) that changed while a trial ran."""
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
