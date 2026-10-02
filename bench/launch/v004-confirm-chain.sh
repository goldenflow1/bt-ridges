#!/bin/bash
# v004 follow-up (authorized 2026-10-01): §5 paired confirmation blocks for the two normal-condition drops
# (baseline 2b2d1281 vs v004 5406e4dd, normal conditions, 3 pairs each), then compare with the confirmation data,
# then held-out G7 only if both verdicts are keep. The upload is never part of this chain.
set -uo pipefail
cd "$(dirname "$0")/../.."
BASE=submissions/v001/agent.py          # 2b2d1281: the bundle the promoted baselines measured
CAND=bench/variants/v004-b2b3-5406e4dd.py
DEV=bench/runs/20261001-121805-dev
PUB=bench/runs/20261001-135021-public
RIDGES="uv run --project $HOME/bittensor/ridges-cli --no-sync ridges"
SAFE=(--allowance 0.29 --ceiling 30 --keep-headroom 5 --stop-on-billing-mismatch --stop-on-input-change
      --max-blocked-slots 2 --max-consecutive-incomplete 3 --ridges "$RIDGES")
say() { echo "[confirm $(date +%H:%M)] $*"; }
check() { [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ] || { say "REFUSED: $1 hash"; exit 2; }; }
check "$BASE" 2b2d12812ca668a05f79b8a60d1511dceb977353d2094c56a5d1087983fab1d6
check "$CAND" 5406e4dd79608e0109e8d1c283879f63b78099a11cd422193623a4a7f5a49637
newest() { ls -td bench/runs/*-"$1" 2>/dev/null | head -1; }

say "1/3 confirmation: ch-py-tz-buckets x3 pairs (dev, normal)"
uv run python tools/run_bench.py --set dev --tasks ch-py-tz-buckets --repeats 3 --purpose confirmation \
  --agent "$BASE" --agent-b "$CAND" "${SAFE[@]}" --spend-limit 1.00 --experiment-id v004-confirm > bench/runs/v004-confirm-dev.log 2>&1
CDA=$(newest dev-A); CDB=$(newest dev-B)
say "1/3 confirmation: prefix-hierarchy x3 pairs (public, normal)"
uv run python tools/run_bench.py --set public --tasks pg-netbox-prefix-hierarchy-annotations-001 --repeats 3 --purpose confirmation \
  --agent "$BASE" --agent-b "$CAND" "${SAFE[@]}" --spend-limit 1.00 --experiment-id v004-confirm > bench/runs/v004-confirm-public.log 2>&1
CPA=$(newest public-A); CPB=$(newest public-B)
say "runs: $CDA $CDB $CPA $CPB"

ok=1
for spec in "dev-2b2d1281:$DEV:$CDA:$CDB" "public-2b2d1281:$PUB:$CPA:$CPB"; do
  IFS=: read -r base run ca cb <<< "$spec"
  uv run python tools/bench_summary.py compare --reliability "bench/baselines/$base.json" "$run" \
    --confirm-baseline "$ca" --confirm-candidate "$cb" > "bench/runs/v004-compare-confirmed-$base.json" 2>&1
  verdict=$(python3 -c "import json;print(json.load(open('bench/runs/v004-compare-confirmed-$base.json')).get('decision','error'))" 2>/dev/null || echo error)
  say "2/3 compare $base with confirmation: $verdict"
  [ "$verdict" = "keep" ] || ok=0
done
[ "$ok" = 1 ] || { say "STOP: not keep after confirmation (see bench/runs/v004-compare-confirmed-*.json)"; exit 4; }

say "3/3 held-out G7: 7x3 on $CAND"
uv run python tools/run_bench.py --set heldout --repeats 3 --purpose evaluation --agent "$CAND" "${SAFE[@]}" \
  --spend-limit 1.50 --experiment-id v004-g7-b2b3 > bench/runs/v004-g7.log 2>&1
say "held-out run: $(newest heldout)"
say "DONE: ready for the submission gate (upload stays manual)"
