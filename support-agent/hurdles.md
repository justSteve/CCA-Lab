# Hurdles: Rig 01 — Customer Support Resolution Agent

Running log of friction, surprises, and discoveries encountered during this rig.

---

## 2026-04-09: GC session spawn blocked by root + API key

**Category:** Infrastructure blocker
**Impact:** Cannot use GC's native session spawning for Claude Code agents
**Root cause (1):** Claude Code v2.1.97 blocks `--dangerously-skip-permissions` when running as root. GC hardcodes this flag for all `provider = "claude"` sessions.
**Root cause (2):** `ANTHROPIC_API_KEY` is set to "PLACEHOLDER" in the factory image. Non-interactive Claude Code sessions need a real API key; the current session authenticates via OAuth/keychain which doesn't carry to spawned sessions.
**Workaround:** COO uses Agent subagents (same session isolation, different dispatch mechanism) while tracking work via beads and formulas.
**Resolution needed:** Factory image needs either (a) a non-root user for GC sessions, or (b) a real API key in the environment. GC may also need a config option to use `--permission-mode dontAsk` instead of `--dangerously-skip-permissions`.

