#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
cd /app
cp /logs/agent/patch.diff /logs/verifier/graded.patch
if [ -s /logs/verifier/graded.patch ]; then
    git apply --check /logs/verifier/graded.patch
    git apply /logs/verifier/graded.patch
fi
python3 /tests/verify.py
