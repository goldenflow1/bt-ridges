#!/bin/bash
# E016 launcher (docs/plans/e016-protocol.md). Usage: bench/launch/e016.sh pilot x15|x25 | main
# Verifies the frozen inputs, then runs the paired A/B comparison with every protocol limit enforced by run_bench.
set -euo pipefail
cd "$(dirname "$0")/../.."
A=bench/variants/v004-a-only-eb9e6ee.py
B=bench/variants/v004-b2b3-5406e4dd.py
# Main-cohort condition: empty until frozen by a dated protocol amendment after calibration (§3a).
MAIN_CONDITION="x25"  # frozen 2026-10-01 by protocol §3a (x25 calibration pilot passed)
check() { [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ] || { echo "REFUSED: $1 does not match the protocol hash" >&2; exit 2; }; }
scenario_for() {
  case "$1" in
    x15) SCENARIO=bench/faults/cost-x15.json; check "$SCENARIO" 2b8f28ecb53301ea209bfe6defa9b78bac07f81dddee5928154fae0db4a13ae3 ;;
    x25) SCENARIO=bench/faults/cost-x25.json; check "$SCENARIO" f0166642b9c673203a69d8d2be0b0029e65a9255fe890f309f9bbc43e1f7714c ;;
    *) echo "REFUSED: unknown condition '$1' (declared: x15, x25)" >&2; exit 2 ;;
  esac
}
check "$A" d8d965c67e98ed6294cc2ac4448803bee83bb4f9a0ae0003b46e8a7a7d1decfe
check "$B" 5406e4dd79608e0109e8d1c283879f63b78099a11cd422193623a4a7f5a49637
common() {
  COMMON=(--set dev --agent "$A" --agent-b "$B" --fault-scenario "$SCENARIO" --allowance 0.29 --ceiling 30
          --keep-headroom 5 --stop-on-billing-mismatch --stop-on-input-change
          --max-blocked-slots 2 --max-consecutive-incomplete 3
          --ridges "uv run --project $HOME/bittensor/ridges-cli --no-sync ridges")
}
case "${1:-}" in
  pilot)
    scenario_for "${2:-}"; common
    # One pilot envelope for all calibration pilots ($0.50 total).
    exec uv run python tools/run_bench.py "${COMMON[@]}" --purpose diagnostic --repeats 1 --spend-limit 0.50 \
      --experiment-id e016-pilot --tasks py-django-n-plus-one,py-sqla-orders-fanout,ts-prisma-groupby,ch-py-prewhere-orderkey ;;
  main)
    [ -n "$MAIN_CONDITION" ] || { echo "REFUSED: the main-cohort condition is not frozen yet (protocol §3a)" >&2; exit 2; }
    scenario_for "$MAIN_CONDITION"; common
    exec uv run python tools/run_bench.py "${COMMON[@]}" --purpose evaluation --repeats 3 --spend-limit 4.00 \
      --experiment-id e016-main ;;
  *) echo "usage: $0 pilot x15|x25 | main" >&2; exit 2 ;;
esac
