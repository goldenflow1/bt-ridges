#!/usr/bin/env bash
# Ridges submission helper for Bittensor v11, Linux/WSL.
# References: https://www.bittensor.com/docs/migration
#             https://docs.ridges.ai/guides/submit
# Run with bash; do not source. Never run with shell tracing or record key creation.
set +x
set -euo pipefail
umask 077

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WALLET=${RIDGES_WALLET_NAME:-goldenflow-apex}
HOTKEY=${RIDGES_HOTKEY_NAME:-ridge-miner-v2}
CLI_COMMIT=d74410d8484facd59d269e2e875abaad3b355128
CLI_DIR=${RIDGES_CLI_DIR:-"$HOME/.local/share/quarry-ridges-cli-d74410d8"}
SUBMISSION=${RIDGES_SUBMISSION_DIR:-}
AGENT=

die() { printf '%s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || die "Missing command: $1"; }
interactive() { [[ -t 0 && -t 1 ]] || die 'Run this step in an interactive terminal.'; }
confirm_wallet_selection() {
    [[ -n ${RIDGES_WALLET_NAME:-} ]] ||
        die 'Set RIDGES_WALLET_NAME to the wallet you currently control before a paid operation.'
}

usage() {
    cat <<'HELP'
Usage: bash ridges_submit.sh STEP

Run these steps in order on the machine containing your wallet:
  setup       Install the pinned Ridges uploader in its own environment (git + uv).
  status      Show balance and registrations using your installed v11 btcli.
  hotkey      Create ridge-miner-v2 if absent; keep its recovery phrase private.
  register    Preview and register that hotkey on mainnet subnet 62.
  fund        Ask for a TAO amount, preview, then stake to your own SN62 hotkey.
  preflight   Verify the selected ready release and its held-out evidence (no payment).
  upload      Upload the verified ready release to competition 28; prompts for keys/payment.
  resume      Resume a paid upload using its receipt; does not burn again.

Defaults: wallet goldenflow-apex, hotkey ridge-miner-v2, mainnet finney.
Paid operations require RIDGES_WALLET_NAME explicitly (wallet migration may have changed it).
The previously shared ridge-miner hotkey must not be used.
Run from a complete Quarry checkout; submissions/READY selects the approved release.
Overrides: RIDGES_WALLET_NAME, RIDGES_HOTKEY_NAME, RIDGES_SUBMISSION_DIR, RIDGES_CLI_DIR.
RIDGES_AGENT_FILE is no longer accepted: select a release with its manifest and evidence.
HELP
}

bt() {
    need btcli
    btcli "$@" --wallet "$WALLET" --wallet-hotkey "$HOTKEY" \
        --wallet-path "$HOME/.bittensor/wallets" --network finney
}

check_hotkey() {
    [[ $HOTKEY != ridge-miner ]] || die 'Choose a fresh hotkey: ridge-miner was exposed.'
    # Ridges Wallet(name=..., hotkey=...) uses the default wallet directory.
    [[ -z ${BT_WALLET_PATH:-} || $BT_WALLET_PATH == "$HOME/.bittensor/wallets" ]] ||
        die 'This helper requires wallets in ~/.bittensor/wallets for both CLIs.'
    [[ -f "$HOME/.bittensor/wallets/$WALLET/hotkeys/$HOTKEY" ]] ||
        die "Hotkey not found. Run: bash $0 hotkey"
}

check_agent() {
    need python3
    [[ -z ${RIDGES_AGENT_FILE:-} ]] || die 'Use RIDGES_SUBMISSION_DIR to select a verified release.'
    if [[ -n $SUBMISSION ]]; then
        AGENT=$(python3 "$SCRIPT_DIR/submission_preflight.py" "$SUBMISSION") || exit 1
    else
        AGENT=$(python3 "$SCRIPT_DIR/submission_preflight.py") || exit 1
    fi
}

upload() {
    confirm_wallet_selection
    interactive
    check_hotkey
    check_agent
    [[ -x "$CLI_DIR/.venv/bin/ridges" ]] || die "Run: bash $0 setup"
    printf 'Wallet: %s; hotkey: %s; subnet: 62; competition: 28\n' "$WALLET" "$HOTKEY"
    printf '%s\n' 'Enter your OpenRouter runtime and management keys at the hidden prompts.'
    printf '%s\n' 'Save the payment quote ID, block hash, extrinsic index, and returned agent ID.'
    # Use the pinned uploader, not the Bittensor v11 virtual environment.
    # Explicitly use the production API and mainnet for the Alpha burn.
    (
        cd -- "$CLI_DIR"
        export SUBTENSOR_NETWORK=finney
        exec "$CLI_DIR/.venv/bin/ridges" --url https://agent-upload.ridges.ai "$1" \
            --file "$AGENT" --coldkey-name "$WALLET" --hotkey-name "$HOTKEY" --competition 28
    )
}

case ${1:-help} in
    help|-h|--help) usage ;;
    preflight) check_agent; printf 'Verified release: %s\n' "$AGENT" ;;
    setup)
        need git
        need uv
        if [[ ! -e $CLI_DIR ]]; then
            mkdir -p -- "$(dirname -- "$CLI_DIR")"
            git clone https://github.com/ridgesai/ridges.git "$CLI_DIR"
            git -C "$CLI_DIR" checkout --detach "$CLI_COMMIT"
        fi
        [[ $(git -C "$CLI_DIR" rev-parse HEAD) == "$CLI_COMMIT" ]] ||
            die 'Existing uploader checkout has a different revision; use a fresh RIDGES_CLI_DIR.'
        uv sync --project "$CLI_DIR" --python 3.12 --extra miner --locked
        printf '%s\n' 'Uploader ready. Your existing Bittensor environment is unchanged.'
        ;;
    status)
        bt wallet balance
        bt wallet registrations
        ;;
    hotkey)
        interactive
        [[ $HOTKEY != ridge-miner ]] || die 'Choose a fresh hotkey name.'
        need btcli
        [[ -f "$HOME/.bittensor/wallets/$WALLET/coldkeypub.txt" ]] || die "Wallet $WALLET not found."
        if [[ -e "$HOME/.bittensor/wallets/$WALLET/hotkeys/$HOTKEY" ]]; then
            printf 'Keeping existing hotkey %s; no key was overwritten.\n' "$HOTKEY"
        else
            printf '%s\n' 'Save the new recovery phrase privately. Do not paste it into chat.'
            btcli wallet new-hotkey --wallet "$WALLET" --wallet-hotkey "$HOTKEY" \
                --wallet-path "$HOME/.bittensor/wallets"
        fi
        ;;
    register)
        confirm_wallet_selection
        interactive
        check_hotkey
        bt tx burned-register --netuid 62 --dry-run
        bt tx burned-register --netuid 62
        bt wallet registrations
        ;;
    fund)
        confirm_wallet_selection
        interactive
        check_hotkey
        bt wallet balance
        need curl
        need python3
        if ! pricing_json=$(curl --fail --silent --show-error --max-time 30 https://agent-upload.ridges.ai/upload/eval-pricing); then
            die 'Could not fetch the upload price. No stake was submitted; retry fund later.'
        fi
        python3 -c '
import json, sys
try:
    quote = json.load(sys.stdin)
    amount = quote["amount_alpha_rao"]
    if quote["payment_netuid"] != 62 or type(amount) is not int or amount <= 0:
        raise ValueError("unexpected subnet or amount")
except (ValueError, KeyError, TypeError):
    sys.exit("Invalid upload price response. No stake was submitted.")
print("Current upload quote: %.9f SN62 Alpha" % (amount / 1e9))
' <<< "$pricing_json"
        printf '%s\n' 'Upload costs about $5 in burnable SN62 Alpha; this step purchases Alpha with TAO.'
        printf '%s\n' 'Choose the amount after checking the current quote. Leave TAO for transaction fees.'
        read -r -p 'TAO to stake to your own miner (blank cancels): ' stake_amount
        [[ -n $stake_amount ]] || exit 0
        [[ $stake_amount =~ ^[0-9]+([.][0-9]+)?$ && $stake_amount =~ [1-9] ]] || die 'Enter a positive decimal TAO amount.'
        bt tx add-stake --netuid 62 --hotkey "$WALLET/$HOTKEY" --amount-tao "$stake_amount" --dry-run
        bt tx add-stake --netuid 62 --hotkey "$WALLET/$HOTKEY" --amount-tao "$stake_amount"
        ;;
    upload) upload upload ;;
    resume) upload resume-upload ;;
    *) usage; exit 2 ;;
esac
