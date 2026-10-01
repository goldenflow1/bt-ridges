#!/bin/bash
# E016 launcher (docs/plans/e016-protocol.md). Usage: bench/launch/e016.sh pilot|main
# Verifies the frozen inputs, then runs the paired A/B comparison with every protocol limit enforced by run_bench.
set -euo pipefail
cd "$(dirname "$0")/../.."
A=bench/variants/v004-a-only-eb9e6ee.py
B=bench/variants/v004-b2b3-5406e4dd.py
SCENARIO=bench/faults/cost-x15.json
check() { [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ] || { echo "REFUSED: $1 does not match the protocol hash" >&2; exit 2; }; }
check "$A" d8d965c67e98ed6294cc2ac4448803bee83bb4f9a0ae0003b46e8a7a7d1decfe
check "$B" 5406e4dd79608e0109e8d1c283879f63b78099a11cd422193623a4a7f5a49637
check "$SCENARIO" 2b8f28ecb53301ea209bfe6defa9b78bac07f81dddee5928154fae0db4a13ae3
COMMON=(--set dev --agent "$A" --agent-b "$B" --fault-scenario "$SCENARIO" --allowance 0.29 --ceiling 30
        --keep-headroom 5 --stop-on-billing-mismatch --stop-on-input-change
        --max-blocked-slots 2 --max-consecutive-incomplete 3
        --ridges "uv run --project $HOME/bittensor/ridges-cli --no-sync ridges")
case "${1:-}" in
  pilot) exec uv run python tools/run_bench.py "${COMMON[@]}" --purpose diagnostic --repeats 1 --spend-limit 0.50 --experiment-id e016-pilot \
           --tasks py-django-n-plus-one,py-sqla-orders-fanout,ts-prisma-groupby,ch-py-prewhere-orderkey ;;
  main)  exec uv run python tools/run_bench.py "${COMMON[@]}" --purpose evaluation --repeats 3 --spend-limit 4.00 --experiment-id e016-main ;;
  *) echo "usage: $0 pilot|main" >&2; exit 2 ;;
esac
