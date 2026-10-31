#!/bin/sh
set -eu
export LOCAL_MODEL='deepseek-r1:14b'
export CHAT_BACKEND='ollama'
API_KEY_FILE="${HOME}/.molecular-review-api-key"
if [ ! -s "$API_KEY_FILE" ]; then
  umask 077
  python3 -c 'import secrets; print("mg_" + secrets.token_urlsafe(32))' > "$API_KEY_FILE"
fi
export MOLECULAR_CHAT_API_KEY="${MOLECULAR_CHAT_API_KEY:-$(cat "$API_KEY_FILE")}"
exec python3 "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/local-backend.py"
