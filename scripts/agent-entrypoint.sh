#!/bin/bash
set -e

# Defaults
AGGREGATOR_URL="${AGGREGATOR_URL:-http://aggregator:8443}"
SERVER_ID="${SERVER_ID:-$(hostname)}"
SCAN_ROLE="${SCAN_ROLE:-auto}"
REPORT_FILE="/tmp/report.json"

echo "=== infra-auditor agent ==="
echo "Server ID : ${SERVER_ID}"
echo "Role      : ${SCAN_ROLE}"
echo "Aggregator: ${AGGREGATOR_URL}"
echo ""

# Run scan
echo "[1/3] Running scan..."
infra-auditor scan --role "${SCAN_ROLE}" -o "${REPORT_FILE}"
echo "  → Report generated: ${REPORT_FILE}"

# Wait for aggregator to be ready
echo "[2/3] Waiting for aggregator..."
for i in $(seq 1 30); do
    HEALTH_OK=$(python3 -c "
import urllib.request, sys
try:
    resp = urllib.request.urlopen('${AGGREGATOR_URL}/api/v1/health', timeout=2)
    print('OK')
except Exception as e:
    print('FAIL: ' + str(e), file=sys.stderr)
" 2>/dev/null || true)
    if [ "$HEALTH_OK" = "OK" ]; then
        echo "  → Aggregator is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ✗ Aggregator not reachable after 30s"
        exit 1
    fi
    sleep 1
done

# Submit report
echo "[3/3] Submitting report..."
python3 -c "
import json, urllib.request, sys

with open('${REPORT_FILE}') as f:
    report = json.load(f)

payload = json.dumps({'server_id': '${SERVER_ID}', 'report': report}).encode()

req = urllib.request.Request(
    '${AGGREGATOR_URL}/api/v1/reports',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print('  → Response:', resp.read().decode())
except Exception as e:
    print('  ✗ Submit failed:', e, file=sys.stderr)
    sys.exit(1)
"

echo ""
echo "=== Agent completed ==="
