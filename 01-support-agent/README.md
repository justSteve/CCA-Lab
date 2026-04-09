# 01-support-agent: Customer Support Resolution Agent

## Purpose

_Describe what this rig builds and why._

## Rig Structure

```
01-support-agent/
  .beads/          # Work authorization (issues, interactions, routes)
  bin/             # Rig-local scripts
  outputs/         # Deliverable artifacts
  logs/            # Execution logs
  NOTES.md         # Study closure document
  README.md        # This file
  hurdles.md       # Friction and discovery log
  .tmux-layout.sh  # Per-rig tmux session launcher
  .gitignore       # Ignores logs/, outputs/, .env
```

## Usage

```bash
# Launch rig tmux session
bash .tmux-layout.sh

# Run rig scripts
bash bin/<script>.sh
```
