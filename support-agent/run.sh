#!/usr/bin/env bash
# Customer Support Resolution Agent — CLI entry point
#
# Usage:
#   ./run.sh "I want to cancel order #ORD-1001"
#   ./run.sh --interactive
#   ./run.sh --interactive --conversation-id abc123
#
# Requires: ANTHROPIC_API_KEY environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure backend database exists
if [ ! -f "$SCRIPT_DIR/data/backend.db" ]; then
    echo "Seeding mock backend database..."
    python3 "$SCRIPT_DIR/data/seed.py"
fi

# Run the agent
cd "$SCRIPT_DIR"
exec python3 -m src.cli "$@"
