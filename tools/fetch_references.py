#!/usr/bin/env python3
"""Fetch other miners' public agents into references/ (read-only study material; used for the originality check).

Walks the competition leaderboard in rank order and saves agents whose code Ridges serves publicly. Hidden agents
(top of the leaderboard, still evaluating, rejected) are recorded as hidden. Never copy anything from references/
into src/ (see references/README.md).

Usage: python tools/fetch_references.py --set-id 28 --want 10 [--max-probe 60] [--delay 15]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API = "https://agent-upload.ridges.ai"
README = """# references/ — read-only study material

Other miners' public agent files, fetched by `tools/fetch_references.py`, exactly as Ridges serves them.

Rules (see CLAUDE.md):
1. Never copy code, prompts or constants from here into `src/`. Learn an idea, write it yourself, and cite it in an
   ADR or experiment note as `REF set-NN/<folder>/agent.py:<line>`, never in `src/`.
2. Never edit files here; re-run the fetcher instead.
3. `tools/originality_check.py dist/agent.py` compares our bundle against every file here before any upload.
"""


def get(url: str, timeout: float = 60.0) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "quarry-reference-fetch"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc).encode()


def get_with_backoff(url: str, sleep=time.sleep) -> Tuple[int, bytes]:
    for attempt in range(1, 5):
        status, body = get(url)
        if status in (0, 429) or status >= 500:
            sleep(30 * attempt)
            continue
        return status, body
    return status, body


def folder_name(row: Dict) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", str(row.get("name") or "agent").lower()).strip("-") or "agent"
    return f"{name}_v{row.get('version_num')}_{str(row['agent_id'])[:8]}"


def decode_code(body: bytes) -> str:
    """The endpoint returns the file as a JSON string; fall back to raw text."""
    text = body.decode("utf-8", "replace")
    try:
        value = json.loads(text)
        return value if isinstance(value, str) else text
    except ValueError:
        return text


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set-id", type=int, default=28)
    parser.add_argument("--want", type=int, default=10, help="stop after this many saved agents")
    parser.add_argument("--max-probe", type=int, default=60, help="stop after probing this many agents")
    parser.add_argument("--delay", type=float, default=15.0, help="seconds between code requests (rate limit)")
    args = parser.parse_args(argv)

    base = os.path.join(ROOT, "references", "miners", f"set-{args.set_id}")
    os.makedirs(base, exist_ok=True)
    readme = os.path.join(ROOT, "references", "README.md")
    if not os.path.exists(readme):
        with open(readme, "w") as handle:
            handle.write(README)
    index_path = os.path.join(base, "index.json")
    index: Dict[str, Dict] = json.load(open(index_path)) if os.path.exists(index_path) else {}

    status, body = get_with_backoff(f"{API}/evaluation-sets/{args.set_id}/leaderboard")
    if status != 200:
        print(f"leaderboard request failed: HTTP {status}", file=sys.stderr)
        return 1
    rows = [r for r in json.loads(body) if r.get("status") == "finished"]
    rows.sort(key=lambda r: ((r.get("competition_state") or {}).get("rank") or 10**9))

    hashes = {meta["sha256"]: key for key, meta in index.items() if meta.get("sha256")}
    saved = sum(1 for meta in index.values() if meta.get("visibility") == "public")
    probed = 0
    for row in rows:
        if saved >= args.want or probed >= args.max_probe:
            break
        key = folder_name(row)
        if key in index:
            continue
        probed += 1
        time.sleep(args.delay)
        status, body = get_with_backoff(f"{API}/retrieval/agent-code?agent_id={row['agent_id']}")
        state = row.get("competition_state") or {}
        meta = {
            "set_id": args.set_id, "agent_id": row["agent_id"], "name": row.get("name"), "version": row.get("version_num"),
            "rank_at_fetch": state.get("rank"), "score": state.get("final_score"), "cost_usd": row.get("average_cost_usd"),
            "status": state.get("status"), "approved": state.get("approved"), "created_at": row.get("created_at"),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if status == 200:
            code = decode_code(body)
            digest = hashlib.sha256(code.encode()).hexdigest()
            meta.update({"visibility": "public", "sha256": digest, "lines": len(code.splitlines()),
                         "duplicate_of": hashes.get(digest)})
            folder = os.path.join(base, key)
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "agent.py"), "w", encoding="utf-8") as handle:
                handle.write(code)
            with open(os.path.join(folder, "meta.json"), "w") as handle:
                json.dump(meta, handle, indent=1)
            hashes.setdefault(digest, key)
            saved += 1
            print(f"saved  #{meta['rank_at_fetch']} {key} ({meta['lines']} lines){' duplicate of ' + meta['duplicate_of'] if meta['duplicate_of'] else ''}")
        else:
            meta.update({"visibility": f"hidden-http-{status}", "detail": body.decode("utf-8", "replace")[:200]})
            print(f"hidden #{meta['rank_at_fetch']} {key}: HTTP {status}")
        index[key] = meta
        with open(index_path, "w") as handle:
            json.dump(index, handle, indent=1)

    lines = ["| Rank | Agent | Score | Cost | Status | Visibility | Duplicate of |", "|---:|---|---:|---:|---|---|---|"]
    for key, meta in sorted(index.items(), key=lambda kv: kv[1].get("rank_at_fetch") or 10**9):
        cost = meta.get("cost_usd")
        lines.append(f"| {meta.get('rank_at_fetch')} | {key} | {meta.get('score')} | "
                     f"{'' if cost is None else f'${cost:.4f}'} | {meta.get('status')} | {meta.get('visibility')} | "
                     f"{meta.get('duplicate_of') or ''} |")
    with open(os.path.join(base, "INDEX.md"), "w") as handle:
        handle.write(f"# set-{args.set_id} references (fetched {time.strftime('%Y-%m-%d')})\n\n" + "\n".join(lines) + "\n")
    print(f"{saved} public agent(s) saved under {base}; {probed} probed this run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
