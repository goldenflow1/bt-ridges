# Third review: latest fixes rechecked

The ordinary paths covered by the new regressions pass. The full suite is **118 passed in 101.75s**. Three findings remain: F2 is fixed for the original Python helper but not all runtime dependencies; F4 is fixed for a returned Git failure but not a raised handoff exception; F6 is unchanged.

This review retains the accepted policies: repair stray edits, and allow an explicitly labelled last-resort candidate when no passing candidate exists and the patch applies. Neither policy is itself a finding.

| Previous finding | Latest result |
|---|---|
| F1: unnamed method scope | Original reproduction fixed. Discovery freezes the rest of the file; a known target repairs its neighbour; absent target does not accept two method edits. |
| F2: check-generated helper | Original `helper.py` case fixed. Runtime files outside `SOURCE_EXTS` remain invisible; see below. |
| F3: failed checks treated as eligible | Fixed in candidate construction. A required `false` check produces an applicable patch explicitly logged as last-resort, with its failure reason. |
| F4: failed final applicability check | Ordinary failure fixed, including fallback to another applicable candidate. Outer exception handling still returns an unchecked patch. |
| F5: SQL comments conceal transaction control | Original comment cases fixed; quoting and nested-comment regression cases pass. This was a parser check, not a live database transaction test. |
| F6: resolved credentials discarded | Still reproducible. The response document's round-two table covers F1–F5 only. |

## F2 — P1: runtime templates are excluded from evidence identity

Location: `src/quarry/git.py:67–78`, particularly the suffix filter at line 72.

`fingerprint()` includes untracked files only when they end in `SOURCE_EXTS`. Runtime SQL templates such as `query.jinja` do not qualify, although handoff later removes them.

Reproduction in a disposable repository:

1. Start with a tracked `m.py` containing `f()` returning `1`.
2. Restrict the task to editing `m.py`; change `f()` to read `Path(__file__).with_name("query.jinja").read_text()`.
3. Run the statement's check: create `query.jinja` containing `SELECT 2`, then assert `m.f() == "SELECT 2"`.
4. Run handoff, apply its returned patch to the restored repository, and call `m.f()`.

Observed:

```text
candidate.eligible = true
candidate.checks_passed = true
patch applies = true
template survives handoff = false
execution = FileNotFoundError: query.jinja
log = returning candidate; evidence=4.0
```

This executes the returned patch; it does not mock the guard or filesystem. The original Python-helper test now passes, but a source-extension allowlist cannot establish that validation used the delivered filesystem state. Cover run-created files that cleanup can remove, with explicit treatment of disposable caches, or validate the reconstructed deliverable in an isolated tree while detecting newly introduced dependencies. Adding `.jinja` alone leaves the same defect for other runtime formats.

## F4 — P2: a handoff exception preserves the old diff

Location: `src/quarry/shell.py:271–276`.

The outer handler catches an exception from `workflow.handoff(diff)`, logs it, and returns the original `diff`. That bypasses the new applicability requirement.

Fault-injection reproduction: run a normal `f(): return 1` to `return 2` edit while making `GitRepo.undo_run_changes()` raise `OSError`. The agent returns a nonempty patch, leaves the edited worktree in place, and a real `git apply --check` fails against that tree.

```text
patch_returned = true
applies_after_return = false
log = hand-off error: OSError: injected cleanup failure
```

The injected exception models a cleanup failure; this is not evidence that normal handoff is broken. It demonstrates that the explicitly claimed exception-path invariant remains unenforced. On error, retry cleanup and verify a candidate, or return no usable patch. Preserve a diff only after successful applicability verification against the actual final worktree.

## F6 — P2: deduplication still drops valid environment credentials

Location: `src/quarry/profile.py:163–168` and the later environment-target insertion at lines 183–187.

Reproduction: a Django config specifies host `db`, database `shop`, user `app`, and `PASSWORD=get_secret()`. Supply matching `PGHOST`, `PGDATABASE`, `PGUSER`, and a resolved fixture `PGPASSWORD` in the environment.

Observed: one target remains, sourced from `settings.py DATABASES['default'] (unresolved: PASSWORD)`; its password is not the resolved environment password. `add()` discards the complete target because its connection identity matches the unresolved one. Sorting afterward cannot recover it.

Retain and rank complete alternatives, or merge explicitly unresolved fields before deduplication. Add a regression asserting that the selected connection uses the environment credential without printing it.

## Verification and remaining limits

- Full offline suite: **118 passed in 101.75s**.
- Bundle rebuilt; Ruff passed; the generated bundle imported successfully under actual Python 3.9.
- Prescreen: **0 failures**, one existing ClickHouse URL warning.
- Requirement traceability: **76/76** IDs have tests. This measures coverage links, not completeness of assertions.
- Independent probes reran the earlier scope, candidate-label, applicability, SQL-comment, credential, and dirty-workspace cases. Additional probes applied and executed the template-dependent patch and injected the handoff cleanup error.
- Probe scripts for this session: `/tmp/quarry_rereview_probes.py` and `/tmp/quarry_third_review_probes.py`.
- The earlier dirty-workspace caveat still reproduces: a pre-existing staged `notes.txt` edit loses both content and staging. This remains outside the clean-repository competition path; do not claim general start-state preservation.
- No live model/database benchmark or competition submission was run. The earlier fixed-timeout finalization concern and deferred architecture phases were not re-audited in this pass.
- Runtime source and tests were not edited by this review. The submission bundle was regenerated and this review document was added.
