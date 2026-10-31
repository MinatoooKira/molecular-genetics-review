#!/bin/zsh
set -euo pipefail

# SakuraFrp token is kept outside the repository. The token file is created by
# the Sakura launcher and must remain readable only by the local user.
TOKEN_FILE="$HOME/Desktop/MatCh-server/server/.sakura-frp-token"
FRPC="$HOME/Desktop/MatCh-server/server/frpc"
TUNNEL_ID="29729226"

if [[ ! -s "$TOKEN_FILE" ]]; then
  print -u2 "SakuraFrp token file not found: $TOKEN_FILE"
  exit 1
fi
if [[ ! -x "$FRPC" ]]; then
  print -u2 "SakuraFrp frpc not found: $FRPC"
  exit 1
fi

TOKEN="$(cut -d: -f1 "$TOKEN_FILE")"
exec "$FRPC" -f "$TOKEN:$TUNNEL_ID" --traffic_opt 1 --hosts frp-way.com:127.0.0.1
