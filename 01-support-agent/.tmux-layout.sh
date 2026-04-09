#!/usr/bin/env bash
# .tmux-layout.sh — canonical per-rig tmux session
# Creates session cca-<rig-name> with:
#   main pane (70%) | right column (30%): hurdles tail, decision inbox, status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RIG_NAME="$(basename "$SCRIPT_DIR")"
SESSION="cca-${RIG_NAME}"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session $SESSION already exists. Attaching..."
  tmux attach-session -t "$SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" -c "$SCRIPT_DIR" -x 200 -y 50

# Split: main (70%) | right column (30%)
tmux split-window -h -t "$SESSION" -p 30 -c "$SCRIPT_DIR"

# Right column: split into 3 panes vertically
# Top: hurdles tail
tmux send-keys -t "$SESSION:.1" "tail -f '$SCRIPT_DIR/hurdles.md' 2>/dev/null || echo 'No hurdles yet'" Enter

# Middle: decision inbox
tmux split-window -v -t "$SESSION:.1" -p 66 -c "$SCRIPT_DIR"
tmux send-keys -t "$SESSION:.2" "echo '=== Decision Inbox ===' && echo 'Waiting for decisions...'" Enter

# Bottom: status
tmux split-window -v -t "$SESSION:.2" -p 50 -c "$SCRIPT_DIR"
tmux send-keys -t "$SESSION:.3" "echo '=== Status ===' && bd ready 2>/dev/null || echo 'No beads context'" Enter

# Focus main pane
tmux select-pane -t "$SESSION:.0"

echo "Session $SESSION created. Attach with: tmux attach -t $SESSION"
