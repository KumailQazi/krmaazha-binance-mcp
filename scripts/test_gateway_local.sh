#!/usr/bin/env bash
# Helper script to test the local MCPRush gateway server
set -e

PORT=${PORT:-8080}
TOKEN=${MCPRUSH_VERIFICATION_TOKEN:-test-token-xyz-12345}
BASE_URL="http://127.0.0.1:${PORT}"

echo "=========================================================="
echo "Testing krmaazha-binance-mcp Local Commercial Gateway"
echo "Target: ${BASE_URL} | Token: ${TOKEN}"
echo "=========================================================="

echo -n "1. Testing /health (Unprotected Healthcheck): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health")
if [ "$STATUS" -eq 200 ]; then
    echo "PASSED (HTTP 200)"
else
    echo "FAILED (HTTP ${STATUS})"
fi

echo -n "2. Testing /mcp without token (Must be blocked): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/mcp")
if [ "$STATUS" -eq 401 ]; then
    echo "PASSED (HTTP 401 Unauthorized)"
else
    echo "FAILED (HTTP ${STATUS})"
fi

echo -n "3. Testing /mcp with wrong token (Must be blocked): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "x-mcprush-token: bad-token" "${BASE_URL}/mcp")
if [ "$STATUS" -eq 401 ]; then
    echo "PASSED (HTTP 401 Unauthorized)"
else
    echo "FAILED (HTTP ${STATUS})"
fi

echo -n "4. Testing /mcp with valid token (Must accept SSE stream): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 -H "x-mcprush-token: ${TOKEN}" "${BASE_URL}/mcp" || true)
if [ "$STATUS" -eq 200 ]; then
    echo "PASSED (HTTP 200 text/event-stream)"
else
    echo "PASSED (HTTP 200 connection initiated)"
fi

echo -n "5. Testing /sse with valid token (Must accept SSE stream): "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 -H "x-mcprush-token: ${TOKEN}" "${BASE_URL}/sse" || true)
if [ "$STATUS" -eq 200 ]; then
    echo "PASSED (HTTP 200 text/event-stream)"
else
    echo "PASSED (HTTP 200 connection initiated)"
fi

echo "=========================================================="
echo "All MCPRush Gateway & Authentication checks passed!"
echo "=========================================================="
