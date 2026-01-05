#!/bin/bash
# API Endpoint Testing Script
# Tests the /billing/plan-features/all endpoint

BASE_URL="${1:-http://localhost:8000}"
ENDPOINT="${BASE_URL}/api/v1/billing/plan-features/all"

echo "=========================================="
echo "Testing API Endpoint: ${ENDPOINT}"
echo "=========================================="
echo ""

# Test 2.1: Endpoint Response Structure
echo "Test 2.1: Endpoint Response Structure"
echo "--------------------------------------"

response=$(curl -s -w "\n%{http_code}" "${ENDPOINT}")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

echo "HTTP Status: ${http_code}"

if [ "$http_code" = "200" ]; then
    echo "✓ Status: 200 OK"
    
    # Check if response is valid JSON
    if echo "$body" | jq empty 2>/dev/null; then
        echo "✓ Valid JSON response"
        
        # Check for expected plans
        plans=$(echo "$body" | jq -r 'keys[]' 2>/dev/null)
        echo "Plans found: $(echo "$plans" | tr '\n' ' ')"
        
        # Check for features in each plan
        for plan in free pro agency enterprise; do
            features=$(echo "$body" | jq -r ".${plan} | keys | length" 2>/dev/null)
            if [ "$features" != "null" ] && [ "$features" != "0" ]; then
                echo "✓ ${plan}: ${features} features"
            else
                echo "⚠ ${plan}: No features (may indicate empty plan_features table)"
            fi
        done
        
        # Check for flag and limit features
        has_flag=$(echo "$body" | jq -r '[.[] | to_entries[] | select(.value | type == "boolean")] | length' 2>/dev/null)
        has_limit=$(echo "$body" | jq -r '[.[] | to_entries[] | select(.value | type == "number")] | length' 2>/dev/null)
        
        if [ "$has_flag" != "0" ]; then
            echo "✓ Flag features present (boolean values)"
        else
            echo "⚠ No flag features found"
        fi
        
        if [ "$has_limit" != "0" ]; then
            echo "✓ Limit features present (numeric values)"
        else
            echo "⚠ No limit features found"
        fi
        
    else
        echo "✗ Invalid JSON response"
        echo "Response body: ${body:0:200}"
    fi
else
    echo "✗ Unexpected status code: ${http_code}"
    echo "Response: ${body:0:200}"
fi

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="

