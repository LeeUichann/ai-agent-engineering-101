#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

: "${MARKET_OWNER:?Set MARKET_OWNER interactively in this terminal; never put the code in a file.}"
for required in .venv/bin/python shop_key.pem buyer_key.pem pricing_policy.json; do
  if [[ ! -f "$required" ]]; then
    printf 'Missing %s. Restore the existing environment/key link; do not generate a new identity.\n' "$required" >&2
    exit 1
  fi
done
export PATH="$HOME/.local/bin:$PATH"
unset MARKET_MEMORY_PATH
printf 'Start only after the old week-07 kit has stopped. This uses the same shop name and keys.\n'
exec .venv/bin/python ../../../scripts/market_kit.py join \
  --dir "$PWD" \
  --market https://market.ourolabs.ai/ \
  --name leeuichann \
  --tunnel
