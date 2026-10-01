#!/bin/bash
# v004 chain (authorized 2026-10-01): E016 confirmation block -> §5 decision -> normal-condition comparison of the
# chosen bundle against the promoted baselines -> held-out G7. Stops at the first failed or undecidable step.
# The upload is never part of this chain.
set -uo pipefail
cd "$(dirname "$0")/../.."
A=bench/variants/v004-a-only-eb9e6ee.py
B=bench/variants/v004-b2b3-5406e4dd.py
RIDGES="uv run --project $HOME/bittensor/ridges-cli --no-sync ridges"
SAFE=(--allowance 0.29 --ceiling 30 --keep-headroom 5 --stop-on-billing-mismatch --stop-on-input-change
      --max-blocked-slots 2 --max-consecutive-incomplete 3 --ridges "$RIDGES")
say() { echo "[chain $(date +%H:%M)] $*"; }
newest() { ls -td bench/runs/*-"$1" 2>/dev/null | head -1; }

say "1/4 E016 confirmation block: ch-py-replacing-final x3 pairs (x25)"
bench/launch/e016.sh confirm ch-py-replacing-final > bench/runs/e016-confirm.log 2>&1
CA=$(newest dev-A); CB=$(newest dev-B)
say "confirmation runs: $CA $CB"

DECISION=$(uv run python - "$CA" "$CB" <<'EOF'
import csv, sys
rows = {arm: list(csv.DictReader(open(f"{d}/results.csv"))) for arm, d in zip("AB", sys.argv[1:3])}
ok = all(len(r) == 3 and all(x.get("purpose") == "confirmation" and x.get("validity") == "valid"
                             and x.get("cost_reconciliation") == "matched-proxy" for x in r) for r in rows.values())
if not ok:
    print("pending")      # incomplete or invalid confirmation evidence: no decision (§5)
else:
    solved = {arm: sum(1 for x in r if x["reward"] in ("1", "1.0")) for arm, r in rows.items()}
    # §5: the drop persists if the candidate (B) solves fewer confirmation trials than the baseline (A)
    print(f"reject {solved['A']} {solved['B']}" if solved["B"] < solved["A"] else f"keep {solved['A']} {solved['B']}")
EOF
)
say "2/4 E016 decision: $DECISION"
case "$DECISION" in
  keep*)   CHOSEN=$B; LABEL=b2b3 ;;
  reject*) CHOSEN=$A; LABEL=a-only ;;
  *) say "STOP: confirmation evidence incomplete; no decision"; exit 3 ;;
esac
echo "$DECISION $CHOSEN" > bench/runs/v004-decision.txt
say "v004 bundle: $CHOSEN ($(sha256sum "$CHOSEN" | cut -c1-16))"

say "3/4 normal-condition comparison: dev 17x3"
uv run python tools/run_bench.py --set dev --repeats 3 --purpose evaluation --agent "$CHOSEN" "${SAFE[@]}" \
  --spend-limit 3.00 --experiment-id "v004-normal-$LABEL" > bench/runs/v004-normal-dev.log 2>&1
DEV=$(newest dev)
say "3/4 normal-condition comparison: NetBox 6x3"
uv run python tools/run_bench.py --set public --repeats 3 --purpose evaluation --agent "$CHOSEN" "${SAFE[@]}" \
  --spend-limit 3.00 --experiment-id "v004-normal-$LABEL" > bench/runs/v004-normal-public.log 2>&1
PUB=$(newest public)
for pair in "dev-2b2d1281:$DEV" "public-2b2d1281:$PUB"; do
  base=${pair%%:*}; run=${pair#*:}
  uv run python tools/bench_summary.py compare --reliability "bench/baselines/$base.json" "$run" > "bench/runs/v004-compare-$base.json" 2>&1
  verdict=$(python3 -c "import json;print(json.load(open('bench/runs/v004-compare-$base.json')).get('decision','error'))" 2>/dev/null || echo error)
  say "compare $base vs $run: $verdict"
  [ "$verdict" = "keep" ] || { say "STOP: normal-condition comparison did not pass ($base: $verdict)"; exit 4; }
done

say "4/4 held-out G7: 7x3"
uv run python tools/run_bench.py --set heldout --repeats 3 --purpose evaluation --agent "$CHOSEN" "${SAFE[@]}" \
  --spend-limit 1.50 --experiment-id "v004-g7-$LABEL" > bench/runs/v004-g7.log 2>&1
say "held-out run: $(newest heldout)"
say "DONE: ready for the submission gate on $CHOSEN (upload stays manual)"
