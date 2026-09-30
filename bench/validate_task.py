#!/usr/bin/env python3
"""Validity gate for practice tasks (bench-catalog.md, B-VALID-01..05).

Usage: python3 bench/validate_task.py bench/tasks/dev/<task-id> [--rmi] [--keep]

Builds the task's environment and verifier compose projects and checks:

  B-VALID-01  empty patch                       -> reward 0
  B-VALID-02  solution/solve.sh patch           -> reward 1
  B-VALID-03  each tests/decoys/*.patch         -> reward 0 (patch must apply)
  B-VALID-04  named checks in instruction.md pass on the unmodified environment
              and leave no stray files in /app
  B-VALID-05  solution + extra new file, solution + extra edited file,
              solution + mode change            -> reward 0
  B-VALID-06  all of the above run on an internal (no-egress) docker network,
              so B-VALID-02/04 passing shows no run-time network is needed

The solution patch is produced the way the Ridges harness does it: a git
baseline of /app is committed in a fresh environment container, solve.sh runs,
and `git diff --binary` against the baseline is the patch.

Each verifier run gets a fresh compose project (pristine DB and /app).
Containers, networks and volumes are always removed; images are kept for
faster re-runs unless --rmi is given.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GIT_ID = ["-c", "user.email=validator@ridges.invalid", "-c", "user.name=validator"]


sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner_results import detect_runner  # noqa: E402
from runner_results import parse as parse_results  # noqa: E402

SCOPE_CHECK = re.compile(r"conservation|bounded|construct|transported|compilation|lint|gofmt|vet|typecheck|model_state")
# Checks that only a scope/conservation problem should trip (B-VALID-09): compile/lint/typecheck must still pass.
SCOPE_ONLY = re.compile(r"conservation|bounded|transported|model_state")
VISIBLE_CHECK = re.compile(r"regression|focused|upstream")


def behaviour_evidence(text, expect):
    """(ok, detail): every declared test executed and failed an assertion, and nothing errored (B-VALID-08)."""
    results = parse_results(text, detect_runner(text))
    errors = sorted(name for name, status in results.items() if status == "error")
    missing = [e for e in expect if not any(e in name and status == "fail" for name, status in results.items())]
    fails = sorted(name for name, status in results.items() if status == "fail")
    ok = bool(fails) and not errors and not missing
    return ok, f"assertion failures={len(fails)} errors={errors} missing={missing}"


RIDGES_BASELINE = Path.home() / "bittensor" / "ridges-cli" / "miners" / "baseline-requirements.txt"


def runtime_dists(task):
    """Packages the Ridges miner runtime expects in the task image (its baseline requirements)."""
    for path in (Path(task) / "environment" / "baseline-requirements.txt", RIDGES_BASELINE):
        if path.exists():
            return [line.split("==")[0].strip() for line in path.read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    return []


def extra_file_content(path, sibling_text):
    """A harmless, valid file for the scope variant in the target's language (B-VALID-09)."""
    suffix = Path(path).suffix
    if suffix == ".py":
        return "# extra helper\n"
    if suffix == ".go":
        match = re.search(r"^package (\w+)", sibling_text or "", re.M)
        return f"package {match.group(1) if match else 'main'}\n"
    if suffix in (".ts", ".tsx", ".js", ".mjs", ".cjs"):
        return "export {};\n"
    return "\n"


class Failure(Exception):
    pass


def sh(cmd, *, timeout=1800, check=True, input_text=None):
    result = subprocess.run(
        cmd,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if check and result.returncode:
        raise Failure(
            f"command failed ({result.returncode}): {' '.join(map(str, cmd))}\n"
            f"{result.stdout[-4000:]}"
        )
    return result


def compose_services(compose_file):
    """Tiny parser: service name -> has build: (no YAML dependency)."""
    services = {}
    current = None
    in_services = False
    for line in Path(compose_file).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            in_services = line.rstrip() == "services:"
            current = None
            continue
        if not in_services:
            continue
        match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if match:
            current = match.group(1)
            services[current] = False
        elif current and re.match(r"^    build:", line):
            services[current] = True
    return services


class Project:
    """One compose project: the task's compose file plus a generated `main`."""

    def __init__(self, name, directory, workdir, image_prefix):
        self.name = name
        self.directory = Path(directory).resolve()
        self.compose = self.directory / "docker-compose.yaml"
        self.override = Path(workdir) / f"{name}.override.yaml"
        services = compose_services(self.compose)
        if "main" in services:
            raise Failure(f"{self.compose} already defines a main service")
        lines = ["services:"]
        for service, has_build in services.items():
            if has_build:
                lines += [f"  {service}:", f"    image: {image_prefix}-{service}:latest"]
        lines += [
            "  main:",
            f"    image: {image_prefix}-main:latest",
            "    build:",
            f"      context: {self.directory}",
            "      dockerfile: Dockerfile",
            '    command: ["sh", "-c", "sleep infinity"]',
        ]
        if services:
            lines.append("    depends_on:")
            for service in services:
                lines += [f"      {service}:", "        condition: service_healthy"]
        # B-VALID-06: every run happens on an internal network without egress.
        lines += ["networks:", "  default:", "    internal: true"]
        self.override.write_text("\n".join(lines) + "\n")
        self.images = [f"{image_prefix}-{s}:latest" for s, b in services.items() if b]
        self.images.append(f"{image_prefix}-main:latest")

    def compose_cmd(self, *args):
        return [
            "docker", "compose", "-p", self.name,
            "--project-directory", str(self.directory),
            "-f", str(self.compose), "-f", str(self.override), *args,
        ]

    def build(self):
        started = time.time()
        sh(self.compose_cmd("build"), timeout=3600)
        return time.time() - started

    def up(self):
        self.down()
        sh(self.compose_cmd("up", "-d", "--wait", "--wait-timeout", "600"), timeout=900)

    def down(self):
        sh(self.compose_cmd("down", "-v", "--remove-orphans", "--timeout", "5"),
           check=False, timeout=300)

    def exec(self, script, *, timeout=1800, check=True, user=None):
        args = ["exec", "-T"]
        if user:
            args += ["-u", user]
        return sh(self.compose_cmd(*args, "main", "bash", "-c", script),
                  timeout=timeout, check=check)

    def container(self):
        out = sh(self.compose_cmd("ps", "-q", "main")).stdout.strip()
        if not out:
            raise Failure("main container is not running")
        return out.splitlines()[0]

    def copy_in(self, local, remote):
        sh(["docker", "cp", str(local), f"{self.container()}:{remote}"])

    def read(self, remote):
        result = self.exec(f"cat {shlex.quote(remote)}", check=False)
        return result.stdout if result.returncode == 0 else None


def regression_block(instruction):
    text = Path(instruction).read_text()
    match = re.search(
        r"Run these checks before finishing:\s*\n+```(?:bash|sh)\n(.*?)\n```", text, re.S
    )
    if not match:
        raise Failure("instruction.md has no 'Run these checks before finishing:' bash block")
    return match.group(1)


def patched_files(patch_text):
    return re.findall(r"^diff --git a/(\S+) b/\S+$", patch_text, re.M)


def junit_failures(xml_text):
    if not xml_text:
        return None
    names = re.findall(r'<testcase name="([^"]+)"\s*>\s*<failure', xml_text)
    return names


class Validator:
    def __init__(self, task_dir, keep_images, keep_containers):
        self.task = Path(task_dir).resolve()
        self.task_id = self.task.name
        self.keep_images = keep_images
        self.keep_containers = keep_containers
        self.rows = []
        self.timings = {}
        self.workdir = Path(tempfile.mkdtemp(prefix=f"validate-{self.task_id}-"))
        slug = re.sub(r"[^a-z0-9]+", "-", self.task_id.lower()).strip("-")
        tag = f"{os.getpid()}"
        self.env = Project(f"rbv-{slug}-{tag}-env", self.task / "environment",
                           self.workdir, f"rbv-{slug}-env")
        self.ver = Project(f"rbv-{slug}-{tag}-ver", self.task / "tests",
                           self.workdir, f"rbv-{slug}-ver")

    def record(self, check_id, name, expected, got, ok, detail=""):
        self.rows.append((check_id, name, expected, got, "PASS" if ok else "FAIL", detail))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {check_id} {name}: expected={expected} got={got} {detail}",
              flush=True)

    # ------------------------------------------------------------------ env side
    def environment_phase(self):
        solve = self.task / "solution" / "solve.sh"
        block = regression_block(self.task / "instruction.md")
        self.env.up()
        # Harness-style baseline before anything runs.
        self.env.exec(
            "cd /app && test ! -e .git && git init -q && git add -A && "
            f"git {' '.join(GIT_ID)} commit -qm baseline"
        )
        # B-VALID-11: the Ridges miner runtime can start here (python3 + its baseline packages, no install needed).
        dists = runtime_dists(self.task)
        probe = (f"import importlib.metadata as m, sys\nmissing = []\nfor d in {dists!r}:\n    try:\n        m.version(d)\n"
                 "    except m.PackageNotFoundError:\n        missing.append(d)\nprint(' '.join(missing))\n"
                 "sys.exit(1 if missing else 0)\n")
        result = self.env.exec(f"python3 -c {shlex.quote(probe)}", check=False, user="1000")
        ok = result.returncode == 0
        self.record("B-VALID-11", "miner runtime prerequisites in the task image", "python3 + baseline packages",
                    "ok" if ok else "missing", ok, "" if ok else result.stdout[-400:])
        # B-VALID-04: named checks on the unmodified repo.
        script = "set -euo pipefail\ncd /app\n" + block + "\n"
        result = self.env.exec(script, check=False, timeout=1800)
        stray = self.env.exec("cd /app && git status --porcelain", check=False).stdout.strip()
        ok = result.returncode == 0 and not stray
        detail = "" if ok else (
            f"exit={result.returncode} stray={stray[:300]!r} tail={result.stdout[-1500:]!r}"
        )
        self.record("B-VALID-04", "named checks pass on unmodified repo", "exit 0, clean tree",
                    f"exit {result.returncode}{', stray files' if stray else ''}", ok, detail)
        (self.workdir / "regression.log").write_text(result.stdout)

        # Solution patch.
        self.env.copy_in(solve, "/tmp/solve.sh")
        result = self.env.exec("bash /tmp/solve.sh", check=False, timeout=1800)
        if result.returncode:
            raise Failure(f"solve.sh failed:\n{result.stdout[-3000:]}")
        patch = self.env.exec("cd /app && git add -A && git diff --cached --binary HEAD").stdout
        if not patch.strip():
            raise Failure("solve.sh produced an empty patch")
        (self.workdir / "solution.patch").write_text(patch)
        touched = patched_files(patch)
        if not touched:
            raise Failure("could not read the files touched by the solution patch")
        # Variants: a new file next to the first touched file, an edit to a
        # tracked file the solution does not touch, a mode change on a
        # touched file.
        allowed = touched[0]
        others = [
            line for line in self.env.exec("cd /app && git ls-files").stdout.splitlines()
            if line not in touched
        ]
        if not others:
            raise Failure("no other tracked file to use for the extra-file variant")
        other = sorted(others, key=lambda p: (not p.endswith((".md", ".txt")), p))[0]
        extra = str(Path(allowed).parent / f"extra_helper{Path(allowed).suffix}")
        qa, qo, qe = map(shlex.quote, (allowed, other, extra))
        variants = {
            "solution + new file": (
                f"printf '%s' {shlex.quote(extra_file_content(extra, self.env.exec(f'cat {qa}', check=False).stdout))}"
                f" > {qe}", f"rm -f {qe}"),
            "solution + edit to other file": (
                f"printf '\\n' >> {qo}", f"git checkout -q -- {qo}"),
            "solution + mode change on allowed file": (
                f"chmod 755 {qa}", f"chmod 644 {qa}"),
        }
        self.variant_patches = {}
        for label, (make, undo) in variants.items():
            text = self.env.exec(
                f"cd /app && {make} && git add -A && git diff --cached --binary HEAD; "
                f"rc=$?; git reset -q; {undo}; exit $rc"
            ).stdout
            if text == patch:
                raise Failure(f"variant '{label}' did not change the patch")
            path = self.workdir / (re.sub(r"\W+", "_", label) + ".patch")
            path.write_text(text)
            self.variant_patches[label] = path
        self.env.down()
        return self.workdir / "solution.patch"

    # ------------------------------------------------------------- verifier side
    def verify(self, patch_path):
        self.ver.up()
        try:
            self.ver.exec("mkdir -p /logs/agent /logs/verifier /logs/artifacts")
            self.ver.copy_in(patch_path, "/logs/agent/patch.diff")
            result = self.ver.exec("bash /tests/test.sh", check=False, timeout=1800)
            reward = (self.ver.read("/logs/verifier/reward.txt") or "").strip()
            junit = self.ver.read("/logs/verifier/junit.xml")
            commands = self.ver.exec(
                "cat /logs/verifier/command-*.log 2>/dev/null", check=False
            ).stdout
        finally:
            self.ver.down()
        log = self.workdir / (Path(patch_path).stem + ".verifier.log")
        log.write_text(result.stdout + "\n\n" + (junit or "<no junit>") + "\n\n" + commands)
        return reward, junit_failures(junit), result.stdout + "\n\n" + commands

    def verifier_phase(self, solution_patch):
        empty = self.workdir / "empty.patch"
        empty.write_text("")

        reward, failed, out = self.verify(empty)
        self.record("B-VALID-01", "empty patch", "0", reward,
                    reward == "0" and failed is not None,
                    f"failed={failed}")
        ok, detail = behaviour_evidence(out, [])
        self.record("B-VALID-08", "empty patch fails by assertion", "assertions, no errors",
                    "ok" if ok else "no", ok, detail)

        reward, failed, out = self.verify(solution_patch)
        self.record("B-VALID-02", "solution patch", "1", reward, reward == "1",
                    "" if reward == "1" else f"failed={failed} tail={out[-800:]!r}")

        decoys = sorted((self.task / "tests" / "decoys").glob("*.patch"))
        if not decoys:
            self.record("B-VALID-03", "decoys present", ">=1", "0", False)
        for decoy in decoys:
            reward, failed, out = self.verify(decoy)
            applied = failed is not None
            # A decoy must be caught by behaviour (hidden/regression tests),
            # not merely by the scope and tree-conservation guards.
            scope_only = applied and bool(failed) and all(
                SCOPE_CHECK.search(name) for name in failed
            )
            semantic = applied and any(not SCOPE_CHECK.search(name) for name in failed or [])
            got = f"{reward}{'' if applied else ' (not applied)'}"
            if scope_only:
                got += " (scope only)"
            self.record("B-VALID-03", f"decoy {decoy.name}", "0 (semantic)", got,
                        reward == "0" and semantic,
                        f"failed={failed}" if applied else f"tail={out[-600:]!r}")
            meta_path = decoy.with_suffix(".json")
            if not meta_path.exists():
                self.record("B-VALID-08", f"decoy {decoy.name} declared", "tests/decoys/*.json", "missing", False)
                continue
            meta = json.loads(meta_path.read_text())
            ok, detail = behaviour_evidence(out, meta.get("expect_failing") or [])
            if meta.get("passes_visible", True):
                visible_failed = [name for name in failed or [] if VISIBLE_CHECK.search(name)]
                ok = ok and not visible_failed
                detail += f" visible_failed={visible_failed}"
            self.record("B-VALID-08", f"decoy {decoy.name} fails its declared test",
                        ", ".join(meta.get("expect_failing") or []), "ok" if ok else "no", applied and ok, detail)

        for label, path in self.variant_patches.items():
            reward, failed, out = self.verify(path)
            applied = failed is not None
            self.record("B-VALID-05", label, "0 (applied)",
                        f"{reward}{'' if applied else ' (not applied)'}",
                        reward == "0" and applied,
                        f"failed={failed}" if applied else f"tail={out[-600:]!r}")
            isolated = applied and bool(failed) and all(SCOPE_ONLY.search(name) for name in failed)
            self.record("B-VALID-09", f"{label}: only scope checks reject it", "scope/conservation only",
                        "ok" if isolated else "no", isolated, f"failed={failed}")

    # ---------------------------------------------------------------------- run
    def run(self):
        print(f"== validating {self.task_id} (logs: {self.workdir})", flush=True)
        try:
            for part in ("task.toml", "instruction.md", "solution/solve.sh",
                         "environment/Dockerfile", "environment/docker-compose.yaml",
                         "tests/Dockerfile", "tests/docker-compose.yaml", "tests/test.sh",
                         "tests/verify.py"):
                if not (self.task / part).is_file():
                    raise Failure(f"missing {part}")
            print("-- building environment", flush=True)
            self.timings["environment build"] = self.env.build()
            print("-- building verifier", flush=True)
            self.timings["verifier build"] = self.ver.build()
            started = time.time()
            solution = self.environment_phase()
            self.timings["environment phase"] = time.time() - started
            started = time.time()
            self.verifier_phase(solution)
            self.timings["verifier runs"] = time.time() - started
            by_id = {}
            for row in self.rows:
                by_id.setdefault(row[0], []).append(row[4] == "PASS")
            offline = all(by_id.get("B-VALID-02", [False])) and all(by_id.get("B-VALID-04", [False]))
            self.record("B-VALID-06", "named checks + grading ran without network egress",
                        "B-02 and B-04 pass offline", "yes" if offline else "no", offline)
        except Failure as error:
            self.record("SETUP", "harness", "ok", "error", False, str(error)[-2000:])
        except subprocess.TimeoutExpired as error:
            self.record("SETUP", "harness", "ok", "timeout", False, str(error)[-500:])
        finally:
            if not self.keep_containers:
                self.env.down()
                self.ver.down()
            if self.keep_images:
                pass
            else:
                sh(["docker", "image", "rm", "-f", *self.env.images, *self.ver.images],
                   check=False)
        return self.report()

    def report(self):
        print()
        print(f"Task: {self.task_id}")
        headers = ("ID", "Check", "Expected", "Got", "Result")
        rows = [row[:5] for row in self.rows]
        widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
        line = "+".join("-" * (w + 2) for w in widths)
        print(line)
        print("|".join(f" {h:<{w}} " for h, w in zip(headers, widths)))
        print(line)
        for row in rows:
            print("|".join(f" {str(c):<{w}} " for c, w in zip(row, widths)))
        print(line)
        for key, seconds in self.timings.items():
            print(f"{key}: {seconds:.0f}s")
        failed = [row for row in self.rows if row[4] != "PASS"]
        print(f"RESULT: {'PASS' if not failed and self.rows else 'FAIL'} "
              f"({len(self.rows) - len(failed)}/{len(self.rows)} checks)")
        print(f"logs: {self.workdir}")
        return 1 if failed or not self.rows else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("task_dir")
    parser.add_argument("--rmi", action="store_true", help="remove built images afterwards")
    parser.add_argument("--keep", action="store_true",
                        help="leave the last containers running (debugging)")
    args = parser.parse_args()
    def terminate(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, terminate)
    if not shutil.which("docker"):
        print("docker not found", file=sys.stderr)
        return 2
    return Validator(args.task_dir, not args.rmi, args.keep).run()


if __name__ == "__main__":
    sys.exit(main())
