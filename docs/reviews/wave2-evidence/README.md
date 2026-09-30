# Wave 2 task calibration evidence

Full Docker calibration is complete: **12/12 tasks, 196/196 checks, 26 behavioral decoys and 36 scope variants passed**. These are task-validity results, not agent solve trials or a promoted baseline. No miner inference calls were made.

To reproduce one task from the repository root:

```sh
python3 bench/validate_task.py bench/tasks/dev/<task-id>
```

Image builds fetch dependencies. The application checks and grading then run on internal Docker networks without internet access. Run tasks serially on this host.

## Records

- `serial-results.json` records the first complete batch, source digests, exit status and elapsed time. Each task's `.validation.log` contains the validity matrix; its `.artifacts/` directory contains the reference, empty-patch, decoy and scope-probe logs.
- [retry-results.json](retry-results.json) records complete passing reruns after repairs and template cleanup. Failed attempts remain available and are not replaced with successful logs.
- [final-results.json](final-results.json) selects the accepted attempt per task and records successful assertion-log replay, application-copy identity and current/validated source digests.
- [cleanup.json](cleanup.json) confirms no containers, networks or volumes remain for any recorded validation project. Cached images are retained for reuse.
- `python-pg-instruction-clarifications.json` documents two post-validation instruction-only additions disclosing existing checker size limits. The executable calibration inputs and named regression commands are unchanged; removing the recorded paragraphs reconstructs the original validated task digests.
- `automatic-gates-final.txt` records G0–G5 after the assertion-parser repair. It does not close the separate B2 baseline/runtime-identity requirements.
- [automatic-gates-precommit.txt](automatic-gates-precommit.txt) records the passing G0–G5 rerun after pulling the subsequent B2 and public-reconnaissance commits (92/92 requirements traced).

## Preserved failed attempts

The first `py-sqla-latest-per-customer` attempt exposed a psycopg fixture-formatting error. Its `.initial.validation.log` and `.initial.artifacts/` preserve that failure. The repaired task subsequently passed a complete rerun.

The first `ch-py-uniq-exact` attempt rejected an approximate-count decoy that also failed a visible empty-input case. Its initial batch log is retained. The repair normalizes an empty approximate count to zero while preserving the hidden high-cardinality error; its complete rerun passed 16/16.

The first `ts-ch-client-limit-by` attempt rejected a malformed global-limit decoy. An overly broad text replacement damaged `ORDER BY` as well as changing `LIMIT ... BY`; the corrected decoy retains valid ordering and applies a global quota. Its initial 15/16 result remains in the batch records. Both TypeScript tasks passed complete 16/16 reruns after removal of unused template settings and checker constants; the ClickHouse images no longer install an unused PostgreSQL client.

The initial PostgreSQL failure also exposed an assertion-parser bug: another test's summary could hide a runtime error. The parser now isolates traceback sections and checks the terminal exception. Regression tests cover sibling-summary contamination and misleading exception messages/chains; final evidence is replayed with that parser.
