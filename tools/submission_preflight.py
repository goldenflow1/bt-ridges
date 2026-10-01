"""Verify a frozen release before invoking the paid uploader (B-RUN-05)."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.bench_summary import SummaryError  # noqa: E402
from tools.submission_gate import evaluate, sha256_file  # noqa: E402


def preflight(submission, refs=None):
    folder = Path(submission).resolve()
    manifest = json.loads((folder / 'manifest.json').read_text())
    agent = folder / 'agent.py'
    if manifest.get('status') != 'ready' or manifest.get('sha256') != sha256_file(str(agent)):
        raise ValueError('release is not ready or agent checksum differs from its manifest')
    if manifest.get('competition_set_id') != 28:
        raise ValueError('this uploader requires competition 28')
    run = folder / 'evidence' / 'heldout'
    evidence = manifest.get('evidence_sha256') or {}
    for name in ('manifest.json', 'results.csv'):
        if evidence.get(name) != sha256_file(str(run / name)):
            raise ValueError('held-out evidence checksum mismatch: ' + name)
    results, _ = evaluate(str(agent), str(run), str(refs or ROOT / 'references' / 'miners'))
    failures = [name + ': ' + detail for name, passed, detail in results if not passed]
    if failures:
        raise ValueError('submission gate failed: ' + '; '.join(failures))
    return str(agent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('submission', nargs='?', help='release folder; defaults to submissions/READY')
    args = parser.parse_args()
    try:
        folder = args.submission
        if not folder:
            version = (ROOT / 'submissions' / 'READY').read_text().strip()
            if not version or Path(version).name != version:
                raise ValueError('invalid submissions/READY version')
            folder = str(ROOT / 'submissions' / version)
        print(preflight(folder))
        return 0
    except (OSError, ValueError, KeyError, SummaryError) as exc:
        print('Upload blocked: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
