"""B-VALID-08 (decoys fail by an executed assertion) and B-VALID-09 (valid scope-variant files)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "bench"))

from runner_results import detect_runner, parse  # noqa: E402
from validate_task import behaviour_evidence, extra_file_content  # noqa: E402

PYTEST_ASSERT = """
=================================== FAILURES ===================================
_________________________ test_equal_amounts_counted __________________________
    def test_equal_amounts_counted():
>       assert revenue() == 30
E       AssertionError: assert 20 == 30
tests/test_hidden.py:9: AssertionError
=========================== short test summary info ============================
FAILED tests/test_hidden.py::test_equal_amounts_counted - AssertionError: assert 20 == 30
PASSED tests/test_hidden.py::test_empty_customers
"""
PYTEST_SYNTAX = """
==================================== ERRORS ====================================
____________________ ERROR collecting tests/test_hidden.py _____________________
E     SyntaxError: invalid syntax
=========================== short test summary info ============================
ERROR tests/test_hidden.py
collected 0 items / 1 error
"""
PYTEST_NAME_ONLY = """
_________________________ test_equal_amounts_counted __________________________
E       ModuleNotFoundError: No module named 'app'
FAILED tests/test_hidden.py::test_equal_amounts_counted - ModuleNotFoundError: No module named 'app'
"""
DJANGO = """test_a (app.tests.T.test_a) ... FAIL
test_b (app.tests.T.test_b) ... ERROR
test_c (app.tests.T.test_c) ... ok
"""
GO_FAIL = "=== RUN   TestTies\n    store_test.go:40: got [1 2], want [2 1]\n--- FAIL: TestTies (0.1s)\n--- PASS: TestOther (0.1s)\n"
GO_PANIC = "=== RUN   TestTies\npanic: runtime error: index out of range\n"
GO_BUILD = "# app/internal/store\ninternal/store/events.go:12:5: undefined: x\nFAIL\tapp/internal/store [build failed]\n"
TAP = """TAP version 13
not ok 1 - hidden: ordering
  ---
  failureType: 'testCodeFailure'
  code: 'ERR_ASSERTION'
  ...
not ok 2 - hidden: setup
  ---
  failureType: 'hookFailed'
  code: 'ECONNREFUSED'
  ...
ok 3 - hidden: fine
"""
TRUNCATED_XML = ('<testsuite name="t"><testcase name="hidden"><failure message="tail=TAP version 13&#10;'
                 'not ok 1 - hidden: ordering&#10;  failureType: \'testCodeFailure\'&#10;  error: |-&#10;  Expect">'
                 "</failure></testcase></testsuite>\n" + TAP)


def test_B_VALID_08_runner_adapters_separate_assertions_from_errors():
    assert parse(PYTEST_ASSERT, "pytest") == {"test_equal_amounts_counted": "fail", "test_empty_customers": "pass"}
    assert parse(DJANGO, "django") == {"test_a": "fail", "test_b": "error", "test_c": "pass"}
    assert parse(GO_FAIL, "go") == {"TestTies": "fail", "TestOther": "pass"}
    assert parse(GO_PANIC, "go")["TestTies"] == "error"
    assert parse(GO_BUILD, "go")["<build>"] == "error"
    assert parse(TAP, "tap") == {"hidden: ordering": "fail", "hidden: setup": "error", "hidden: fine": "pass"}
    assert [detect_runner(t) for t in (PYTEST_ASSERT, DJANGO, GO_FAIL, TAP)] == ["pytest", "django", "go", "tap"]


def test_B_VALID_08_truncated_xml_copy_does_not_turn_an_assertion_into_an_error():
    assert parse(TRUNCATED_XML, "tap")["hidden: ordering"] == "fail"


def test_B_VALID_08_declared_test_must_fail_by_assertion():
    assert behaviour_evidence(PYTEST_ASSERT, ["test_equal_amounts_counted"])[0]
    assert not behaviour_evidence(PYTEST_ASSERT, ["test_other_name"])[0]  # wrong declared test
    assert not behaviour_evidence(PYTEST_SYNTAX, [])[0]  # the review's syntax-error "decoy"
    assert not behaviour_evidence(PYTEST_NAME_ONLY, ["test_equal_amounts_counted"])[0]  # name matches, but not an assertion
    assert not behaviour_evidence(GO_BUILD, [])[0]
    assert not behaviour_evidence("", [])[0]  # missing report: no evidence


def test_B_VALID_09_extra_files_are_valid_code_in_the_target_language():
    assert extra_file_content("app/extra_helper.py", "") == "# extra helper\n"
    assert extra_file_content("internal/store/extra_helper.go", "// x\npackage store\n") == "package store\n"
    assert extra_file_content("src/extra_helper.ts", "") == "export {};\n"
    compile(extra_file_content("m.py", ""), "m.py", "exec")
