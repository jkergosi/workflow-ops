#!/bin/bash
# Script to clean Python bytecode cache to ensure latest code is loaded
# Run this if you encounter SSE or other runtime errors after code changes

echo "Cleaning Python bytecode cache..."

# Find and remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Find and remove all .pyc files
find . -type f -name "*.pyc" -delete 2>/dev/null

# Find and remove all .pyo files
find . -type f -name "*.pyo" -delete 2>/dev/null

echo "Cache cleanup complete!"
echo ""
echo "Next steps:"
echo "1. Restart the application to load fresh bytecode"
echo "2. Monitor logs for any remaining SSE errors"
