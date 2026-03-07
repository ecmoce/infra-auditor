#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AGGREGATOR_URL="http://localhost:8443"
PASS=0
FAIL=0

log_pass() { echo -e "${GREEN}✓ $1${NC}"; PASS=$((PASS+1)); }
log_fail() { echo -e "${RED}✗ $1${NC}"; FAIL=$((FAIL+1)); }
log_info() { echo -e "${YELLOW}→ $1${NC}"; }

echo "============================================"
echo "  infra-auditor Docker Integration Tests"
echo "============================================"
echo ""

# 1. Check containers
log_info "Checking container status..."
if docker compose ps --format json | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]" 2>/dev/null; then
    log_pass "Docker Compose containers are running"
else
    log_fail "Docker Compose containers check failed"
fi

# 2. Health check
log_info "Testing health endpoint..."
HEALTH=$(curl -sf "${AGGREGATOR_URL}/api/v1/health" 2>/dev/null || echo "FAIL")
if echo "${HEALTH}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['data']['service']=='healthy'" 2>/dev/null; then
    log_pass "Health endpoint returns healthy"
else
    log_fail "Health endpoint check failed: ${HEALTH}"
fi

# 3. Wait for agents to complete
log_info "Waiting for agents to submit reports (up to 60s)..."
for i in $(seq 1 60); do
    REPORT_COUNT=$(curl -sf "${AGGREGATOR_URL}/api/v1/health" 2>/dev/null | \
        python3 -c "import sys,json; print(json.load(sys.stdin)['data'].get('total_reports',0))" 2>/dev/null || echo "0")
    if [ "${REPORT_COUNT}" -ge 4 ] 2>/dev/null; then
        log_pass "All 4 agent reports received (count: ${REPORT_COUNT})"
        break
    fi
    if [ "$i" -eq 60 ]; then
        log_fail "Only ${REPORT_COUNT}/4 reports received after 60s"
    fi
    sleep 1
done

# 4. Dashboard API
log_info "Testing dashboard API..."
DASHBOARD=$(curl -sf "${AGGREGATOR_URL}/api/v1/dashboard" 2>/dev/null || echo "FAIL")
if echo "${DASHBOARD}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='success'" 2>/dev/null; then
    log_pass "Dashboard API returns success"
else
    log_fail "Dashboard API failed: ${DASHBOARD}"
fi

# 5. Compliance API
log_info "Testing compliance API..."
COMPLIANCE=$(curl -sf "${AGGREGATOR_URL}/api/v1/compliance" 2>/dev/null || echo "FAIL")
if echo "${COMPLIANCE}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='success'" 2>/dev/null; then
    log_pass "Compliance API returns success"
else
    log_fail "Compliance API failed: ${COMPLIANCE}"
fi

# 6. Reports API
log_info "Testing reports list API..."
REPORTS=$(curl -sf "${AGGREGATOR_URL}/api/v1/reports" 2>/dev/null || echo "FAIL")
if echo "${REPORTS}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='success'" 2>/dev/null; then
    log_pass "Reports list API returns success"
else
    log_fail "Reports list API failed"
fi

# 7. Individual host reports
log_info "Testing per-host report API..."
for host in test-ubuntu22 test-ubuntu24 test-centos7 test-rocky9; do
    REPORT=$(curl -sf "${AGGREGATOR_URL}/api/v1/reports/${host}" 2>/dev/null || echo "FAIL")
    if echo "${REPORT}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='success'" 2>/dev/null; then
        log_pass "Report for ${host} exists"
    else
        log_fail "Report for ${host} missing"
    fi
done

# 8. Frontend accessibility
log_info "Testing frontend..."
FRONTEND=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:3000/" 2>/dev/null || echo "000")
if [ "${FRONTEND}" = "200" ]; then
    log_pass "Frontend accessible on port 3000"
else
    log_fail "Frontend not accessible (HTTP ${FRONTEND})"
fi

# Summary
echo ""
echo "============================================"
echo "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "============================================"

if [ "${FAIL}" -gt 0 ]; then
    exit 1
fi
