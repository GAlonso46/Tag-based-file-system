#!/bin/bash

# Script to run distributed system tests integration

# Default to localhost if not set
export API_URL=${API_URL:-"http://localhost:8000"}

echo "🚀 Starting Distributed System Tests..."
echo "Target API: $API_URL"

# Check python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 could not be found"
    exit 1
fi

# Install requests if missing (simple check)
pip3 install requests > /dev/null 2>&1

# Run test
python3 tests/test_distributed_flow.py
