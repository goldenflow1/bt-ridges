"""Unit tests: clock, wallet, process runner, git, profile, candidate store (docs/specs/harness.md §1, §2, §4, §6)."""

import os
import time

import pytest

from quarry.clock import Clock, read_timeout_env
from quarry.git import GitRepo
from quarry.proc import ProcessRunner, cap_output
from quarry.profile import EnvProfile, build_profile, select_packs
from quarry.shell import Candidate, CandidateStore
from quarry.wallet import BudgetExhausted, Wallet, is_budget_refusal, read_cap_env
from tests.conftest import write


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_H_SHELL_02_deadline_and_reserve():
    now = FakeTime()
    clock = Clock(1800, now)
    assert clock.reserve == 90  # 5% of 1800 > 60
    assert clock.remaining() == 1710
    small = Clock(600, now)
    assert small.reserve == 60
    assert read_timeout_env({}) == 1500
    assert read_timeout_env({"AGENT_TIMEOUT": "abc"}) == 1500
    assert read_timeout_env({"AGENT_TIMEOUT": "-5"}) == 1500
    assert read_timeout_env({"AGENT_TIMEOUT": "900"}) == 900
    now.t += 5000
    assert clock.expired() and clock.remaining() == 0


def test_H_SHELL_06_phase_slice_never_passes_deadline():
    now = FakeTime()
    clock = Clock(1000, now)
    timer = clock.slice(0.5)
    assert timer.remaining() == 500
    now.t += 800
    late = clock.slice(0.5)  # 500s share but only 140s left before the deadline
    assert late.remaining() == pytest.approx(clock.remaining())
    assert timer.expired()
    assert clock.command_timeout() >= 5


def test_H_WALLET_01_cap_from_env():
    assert read_cap_env({}) == 0.29
    assert read_cap_env({"RIDGES_MAX_COST_USD": "x"}) == 0.29
    assert read_cap_env({"RIDGES_MAX_COST_USD": "0.5"}) == 0.5
    assert Wallet(0.29).spendable == pytest.approx(0.261)


def test_H_WALLET_02_refuses_unaffordable_call():
    wallet = Wallet(0.01, {"m": (1.0, 2.0)})
    assert wallet.can_afford(wallet.estimate("m", 1000, 1000))
    assert not wallet.can_afford(wallet.estimate("m", 5_000_000, 1000))
    with pytest.raises(BudgetExhausted):
        wallet.ensure(1.0)


def test_H_WALLET_03_charges_reported_cost_or_price_table():
    wallet = Wallet(1.0, {"m": (1.0, 2.0)})
    assert wallet.charge("m", {"cost": 0.0123}) == pytest.approx(0.0123)
    assert wallet.charge("m", {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}) == pytest.approx(2.0)
    assert wallet.charge("unknown", {"prompt_tokens": 1_000_000, "completion_tokens": 0}) == pytest.approx(3.0)


def test_H_WALLET_04_budget_refusal_detection():
    assert is_budget_refusal(402, "")
    assert is_budget_refusal(429, '{"error": "max cost exceeded for this run"}')
    assert not is_budget_refusal(429, "rate limited")
    wallet = Wallet(1.0)
    wallet.mark_spent()
    with pytest.raises(BudgetExhausted):
        wallet.ensure(0.0)


def test_H_WALLET_05_phase_cap():
    wallet = Wallet(1.0, {"m": (1.0, 1.0)})
    with wallet.phase("driver", 0.1):
        wallet.charge("m", {"cost": 0.08})
        assert wallet.remaining() == pytest.approx(0.02)
        assert not wallet.can_afford(0.05)
    assert wallet.remaining() == pytest.approx(0.9 - 0.08)
    assert wallet.by_phase["driver"] == pytest.approx(0.08)


def test_H_SHELL_04_children_are_killed(tmp_path):
    runner = ProcessRunner(str(tmp_path))
    started = time.time()
    result = runner.run("sleep 30 & sleep 30; echo never", timeout=1)
    assert result.timed_out and time.time() - started < 10
    runner.kill_all()


def test_H_TOOL_05_output_capping_keeps_errors():
    text = "head\n" + "\n".join(f"line {i}" for i in range(5000)) + "\nAssertionError: boom\n" + "\n".join("x" for _ in range(5000))
    capped = cap_output(text, 3000)
    assert len(capped) < 3600 and capped.startswith("head") and "AssertionError: boom" in capped


def test_H_GIT_01_diff_includes_intent_to_add(make_repo):
    repo = make_repo({"a.py": "A = 1\n"})
    write(repo.root, "a.py", "A = 2\n")
    write(repo.root, "new.py", "N = 1\n")
    repo.intent_to_add("new.py")
    diff = repo.diff()
    assert "+A = 2" in diff and "new.py" in diff


def test_H_GIT_02_apply_check_does_not_touch_worktree(make_repo):
    repo = make_repo({"a.py": "A = 1\n"})
    write(repo.root, "a.py", "A = 2\n")
    diff = repo.diff()
    assert repo.apply_check(diff).ok
    with open(os.path.join(repo.root, "a.py")) as handle:
        assert handle.read() == "A = 2\n"
    assert not repo.apply_check("").ok
    assert not repo.apply_check(diff.replace("-A = 1", "-A = 9")).ok


def test_H_GIT_03_changes_are_classified(make_repo):
    repo = make_repo({"a.py": "A = 1\n", "b.py": "B = 1\n", "c.py": "C = 1\n", "d.sh": "echo\n"})
    write(repo.root, "a.py", "A = 2\n")
    os.remove(os.path.join(repo.root, "b.py"))
    write(repo.root, "u.py", "U = 1\n")
    os.chmod(os.path.join(repo.root, "d.sh"), 0o755)
    changes = GitRepo(repo.root).changed()
    assert changes.modified == ["a.py"]
    assert changes.deleted == ["b.py"]
    assert changes.untracked == ["u.py"]
    assert changes.mode_changed == {"d.sh": "100644"}


SETTINGS = """
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'shop_dev', 'USER': 'app', 'PASSWORD': 'pw', 'HOST': 'db', 'PORT': '',
        'TEST': {'NAME': 'shop_test'},
    }
}
REDIS = {'HOST': 'redis'}
"""


def test_H_PROF_01_languages_and_layers(tmp_path):
    root = str(tmp_path)
    write(root, "requirements.txt", "Django==5.0\npsycopg[binary]\n")
    write(root, "manage.py", "")
    write(root, "svc/go.mod", "module x\nrequire github.com/jmoiron/sqlx v1.3.5\n")
    write(root, "web/package.json", '{"dependencies": {"@prisma/client": "5", "@clickhouse/client": "1"}}')
    write(root, "web/tsconfig.json", "{}")
    write(root, "node_modules/typeorm/package.json", '{"name": "typeorm"}')
    profile = build_profile(root, environ={})
    assert profile.languages == ["python", "go", "typescript"]
    assert {"django", "psycopg", "sqlx", "prisma", "clickhouse-js"} <= set(profile.layers)
    assert "typeorm" not in profile.layers


def test_H_PROF_02_database_discovery(tmp_path):
    root = str(tmp_path)
    write(root, "app/settings/configuration.py", SETTINGS)
    write(root, "config/database.yml", "url: clickhouse://reader:secret@ch:8123/analytics\n")
    profile = build_profile(root, environ={"DATABASE_URL": "postgresql://u:p%40ss@pg:5433/main"})
    pg = [d for d in profile.databases if d.engine == "postgresql"]
    assert pg[0].name == "shop_dev" and pg[0].test_name == "shop_test" and pg[0].port == 5432 and pg[0].host == "db"
    assert any(d.password == "p@ss" and d.port == 5433 for d in pg)
    ch = [d for d in profile.databases if d.engine == "clickhouse"]
    assert ch and ch[0].user == "reader" and ch[0].name == "analytics"


def test_H_PROF_03_tools_and_writable(tmp_path):
    root = str(tmp_path)
    write(root, "a.py", "A = 1\n")
    profile = build_profile(root, ["a.py", "missing/new.py"], environ={})
    assert profile.writable["a.py"] is True
    assert isinstance(profile.tools, dict)
    assert "Languages" in profile.render()


def test_H_PROF_04_pack_selection():
    empty = EnvProfile(root="/x")
    assert select_packs(empty) == ["core"]
    assert "clickhouse" in select_packs(empty, "clickhouse")
    django = EnvProfile(root="/x", languages=["python"], layers=["django"])
    assert select_packs(django) == ["core", "python", "django"]


def test_H_SHELL_05_candidate_store_prefers_eligible_then_evidence_then_smaller():
    store = CandidateStore()
    store.add(Candidate("", 9, True))  # empty diffs are ignored
    store.add(Candidate("x" * 50, 5, False))
    store.add(Candidate("y" * 100, 3, True))
    store.add(Candidate("z" * 40, 3, True))
    assert store.best().diff == "z" * 40
    assert CandidateStore().best() is None
