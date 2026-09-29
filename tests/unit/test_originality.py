"""H-LINT-02: originality check against other miners' public agents."""

import textwrap

from tests.conftest import write
from tools.originality_check import check, compare

OURS = textwrap.dedent('''
    def settle_reservation(wallet, reservation, usage_report):
        """Replace a reservation with the reported cost."""
        reported_cost = usage_report.get("cost")
        if isinstance(reported_cost, (int, float)) and reported_cost >= 0:
            wallet.provider_total += float(reported_cost)
            return float(reported_cost), "provider"
        return None, "unknown"


    def splice_symbol_text(original_text, candidate_text, dotted_symbol_name):
        original_lines = original_text.splitlines(keepends=True)
        candidate_lines = candidate_text.splitlines(keepends=True)
        return "".join(original_lines[:1] + candidate_lines[1:2] + original_lines[2:])
''')

THEIRS = textwrap.dedent('''
    import os


    def run_agent_loop(problem_statement_text, repository_root_path):
        conversation_history = [{"role": "user", "content": problem_statement_text}]
        for iteration_index in range(40):
            conversation_history.append({"role": "assistant", "content": str(iteration_index)})
        return os.path.join(repository_root_path, "patch.diff")
''')


def test_H_LINT_02_unrelated_code_passes(tmp_path):
    cand = write(str(tmp_path), "dist/agent.py", OURS)
    write(str(tmp_path), "refs/set-1/a/agent.py", THEIRS)
    status, report = check(cand, str(tmp_path / "refs"), 15, 30)
    assert status == 0, report


def test_H_LINT_02_identical_file_fails(tmp_path):
    cand = write(str(tmp_path), "dist/agent.py", OURS)
    write(str(tmp_path), "refs/set-1/a/agent.py", OURS)
    status, report = check(cand, str(tmp_path / "refs"), 15, 30)
    assert status == 1 and "identical" in "\n".join(report)


def test_H_LINT_02_reformatted_copy_is_caught_by_shingles():
    # same code, comments changed and lines re-wrapped: line overlap drops, token shingles do not
    reformatted = OURS.replace('"""Replace a reservation with the reported cost."""', '"""Different docstring."""')
    reformatted = reformatted.replace("if isinstance(reported_cost, (int, float)) and reported_cost >= 0:",
                                      "if (isinstance(reported_cost, (int, float))\n                and reported_cost >= 0):")
    reformatted = "# header comment\n" + reformatted.replace("\n\n\n", "\n\n\n# section\n")
    result = compare(OURS, reformatted)
    assert result["shingles"] >= 60, result


def test_H_LINT_02_partial_copy_warns_or_fails(tmp_path):
    cand = write(str(tmp_path), "dist/agent.py", OURS + "\n\n" + THEIRS)
    write(str(tmp_path), "refs/set-1/a/agent.py", THEIRS)
    status, report = check(cand, str(tmp_path / "refs"), 15, 30)
    assert status == 1, report  # a whole copied function is well over 30% of this small candidate


def test_H_LINT_02_no_references_is_not_a_pass(tmp_path):
    cand = write(str(tmp_path), "dist/agent.py", OURS)
    status, _ = check(cand, str(tmp_path / "missing"), 15, 30)
    assert status == 2
