#!/bin/bash

# Verification Test Runner for Entitlement Enforcement
# This script helps run the verification tests with proper setup

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}Entitlement Enforcement Verification Test Runner${NC}"
echo -e "${GREEN}==================================================${NC}"
echo ""

# Check if .env.test exists
if [ ! -f ".env.test" ]; then
    echo -e "${YELLOW}Warning: .env.test file not found${NC}"
    echo "Creating template .env.test file..."
    cat > .env.test << EOF
# API Configuration
API_BASE_URL=http://localhost:8000
BASE_URL=http://localhost:3000

# Test Credentials (UPDATE THESE!)
TEST_TENANT_EMAIL=test-enforcement@example.com
TEST_AUTH_TOKEN=your_test_auth_token_here

# Optional: Override for specific tests
# TEST_TENANT_ID=tenant_id_here
EOF
    echo -e "${YELLOW}Please update .env.test with your test credentials${NC}"
    exit 1
fi

# Load environment variables
export $(cat .env.test | xargs)

# Check if backend is running
echo "Checking backend health..."
BACKEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE_URL}/health" || echo "000")

if [ "$BACKEND_HEALTH" != "200" ]; then
    echo -e "${RED}Error: Backend is not responding at ${API_BASE_URL}${NC}"
    echo "Please start the backend server first:"
    echo "  cd ../n8n-ops-backend && python -m app.main"
    exit 1
fi

echo -e "${GREEN}✓ Backend is running${NC}"

# Check if frontend is running (optional)
FRONTEND_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}" || echo "000")

if [ "$FRONTEND_HEALTH" != "200" ]; then
    echo -e "${YELLOW}Warning: Frontend is not running at ${BASE_URL}${NC}"
    echo "Some UI tests may fail. Start frontend with: npm run dev"
fi

# Check for Playwright installation
if ! command -v npx &> /dev/null; then
    echo -e "${RED}Error: npx not found. Please install Node.js${NC}"
    exit 1
fi

# Install Playwright browsers if needed
if [ ! -d "node_modules/@playwright/test" ]; then
    echo "Installing Playwright..."
    npm install --save-dev @playwright/test
fi

echo ""
echo -e "${GREEN}Running verification tests...${NC}"
echo ""

# Parse command line arguments
TEST_FILTER=""
RUN_MODE="--reporter=list"

while [[ $# -gt 0 ]]; do
    case $1 in
        --ui)
            RUN_MODE="--ui"
            shift
            ;;
        --headed)
            RUN_MODE="--headed --reporter=list"
            shift
            ;;
        --html)
            RUN_MODE="--reporter=html"
            shift
            ;;
        --debug)
            RUN_MODE="--debug"
            shift
            ;;
        --environment)
            TEST_FILTER="-g 'Environment Limit'"
            shift
            ;;
        --team)
            TEST_FILTER="-g 'Team Member'"
            shift
            ;;
        --downgrade)
            TEST_FILTER="-g 'Downgrade'"
            shift
            ;;
        --webhook)
            TEST_FILTER="-g 'Webhook'"
            shift
            ;;
        --retention)
            TEST_FILTER="-g 'Retention'"
            shift
            ;;
        --all)
            TEST_FILTER=""
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--ui|--headed|--html|--debug] [--environment|--team|--downgrade|--webhook|--retention|--all]"
            exit 1
            ;;
    esac
done

# Run the tests
npx playwright test tests/verification $RUN_MODE $TEST_FILTER

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${GREEN}✓ All verification tests passed!${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review the test report (if --html was used)"
    echo "  2. Document the verification results"
    echo "  3. Delete verification tests (Task T016)"
    echo ""
else
    echo ""
    echo -e "${RED}==================================================${NC}"
    echo -e "${RED}✗ Some verification tests failed${NC}"
    echo -e "${RED}==================================================${NC}"
    echo ""
    echo "Debugging steps:"
    echo "  1. Check backend logs for errors"
    echo "  2. Verify database state"
    echo "  3. Run with --ui flag to debug interactively:"
    echo "     ./tests/verification/run-verification.sh --ui"
    echo "  4. Check the README.md for troubleshooting"
    echo ""
    exit 1
fi
