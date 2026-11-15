#!/data/data/com.termux/files/usr/bin/bash
# UAPC Termux worker recovery v1. No secrets, no auto-start, no changes to old agent.
set -euo pipefail
ROOT="https://raw.githubusercontent.com/wafbaiki-debug/UAPC-NM-APK-Builder-Public/main/uapc-termux-worker/v1"
DEST="$HOME/uapc-worker-recovery-v1"
if [ -e "$DEST" ]; then
  echo "STOP: $DEST already exists; not overwriting."; exit 2
fi
STAGE="$(mktemp -d "$HOME/.uapc-worker-stage.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
for f in android_executor.py android_source_worker.py android_executor_service.py source_generator.py source_pipeline.py; do
  curl --fail --location --silent --show-error --max-time 90 "$ROOT/$f" -o "$STAGE/$f"
  test -s "$STAGE/$f" || { echo "Missing $f"; exit 3; }
done
python -m py_compile "$STAGE"/*.py
mv "$STAGE" "$DEST"
trap - EXIT
echo "INSTALLED=$DEST"
echo "Existing ~/uapc-agent preserved. No worker started."
echo "AI health check:"
curl --noproxy '*' --silent --show-error --max-time 10 -i http://127.0.0.1:11434/health || true
echo
echo "Next: confirm backend URL, runner token and isolated build launcher before starting worker."
