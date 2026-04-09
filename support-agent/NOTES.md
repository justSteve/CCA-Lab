# Rig 01: Customer Support Resolution Agent — Study Notes

> CCA-F Lab Deliverable 01. Re-read this on exam day.

---

## Exam Concepts Exercised

### Domain 1: Agentic Architecture & Orchestration (27%)

| Task | Concept | Where in code |
|------|---------|---------------|
| 1.1 | Agentic loop: check `stop_reason`, execute tools, continue | `agent.py:run_agent_turn()` — loops while `stop_reason == "tool_use"` |
| 1.4 | Programmatic prerequisite enforcement | `tools.py:execute_tool()` — blocks `process_refund` until `verified_customer_id` is set by `get_customer` |
| 1.4 | Structured handoff at escalation | `tools.py:_build_handoff_packet()` — ticket ID, customer, attempts, recommended action |
| 1.5 | Hook-like tool interception (prerequisite gate) | `tools.py:193-206` — tool dispatch checks state before execution |

**Exam trap to remember:** The exam's Question 1 tests exactly this: "12% of cases skip get_customer." The answer is ALWAYS programmatic enforcement (hooks/gates), not prompt instructions. Prompts have non-zero failure rate for critical business logic.

### Domain 2: Tool Design & MCP Integration (18%)

| Task | Concept | Where in code |
|------|---------|---------------|
| 2.1 | Sharp tool descriptions: what/inputs/outputs/when/when-NOT | `tools.py:23-155` — all four tools follow the five-part discipline |
| 2.1 | Disambiguation between similar tools | `tools.py` — get_customer vs lookup_order cross-reference in WHEN NOT TO USE |
| 2.2 | Structured error envelope: category, message, remediation, isRetryable | `errors.py` — `error_envelope()` and `success_envelope()` |
| 2.2 | Four error categories with distinct handling | `backend.py` — transient (retry), validation (fix input), business (explain), permission (escalate) |
| 2.2 | Valid empty results ≠ errors | `backend.py:96-99` — no-match returns success with `{customer: null}`, not an error |

**Exam trap to remember:** "analyze_content" vs "analyze_document" misrouting — the fix is ALWAYS better descriptions, not routing layers or tool consolidation (Question 2).

### Domain 4: Prompt Engineering & Structured Output (20%)

| Task | Concept | Where in code |
|------|---------|---------------|
| 4.6 | Session isolation: generator ≠ reviewer | The v1 review was done by a separate agent with NO builder context |
| 4.4 | Validation-retry with specific error feedback | Transient retry in `agent.py:_execute_with_retry()` passes error details |

### Domain 5: Context Management & Reliability (15%)

| Task | Concept | Where in code |
|------|---------|---------------|
| 5.1 | Full conversation fidelity (no progressive summarization) | `state.py` — messages list accumulates without truncation |
| 5.1 | Context summarization ONLY at handoff | `tools.py:_build_handoff_packet()` — constructed at escalation moment only |
| 5.2 | Three valid escalation triggers | `agent.py:52-54` — customer requests, policy exception, inability to progress |
| 5.2 | Self-reported confidence is UNRELIABLE | `agent.py:57-58` — explicitly excluded in system prompt + tool descriptions |
| 5.2 | Sentiment-based escalation is INVALID | `agent.py:58-59` — explicitly excluded |
| 5.3 | Structured error propagation enabling recovery | Error envelope gives agent enough info to decide: retry, fix, explain, or escalate |

**Exam trap to remember:** Question 3 — "self-report confidence 1-10 and threshold" is WRONG. Self-reported confidence is poorly calibrated. The answer is explicit criteria with few-shot examples.

---

## Decisions Made

| Decision | Choice | Rationale | Bead |
|----------|--------|-----------|------|
| Tool naming | Official guide names (`get_customer`, `process_refund`) over lab prompt names | Errata: exam tests these exact names | — |
| Escalation triggers | Removed confidence, added "customer requests human" | Errata: Domain 5.2 explicitly marks self-reported confidence as unreliable | — |
| Error envelope | Added `isRetryable` field | Errata: Domain 2.2 requires this field | — |
| Retry budget | 3 transient failures global, 2 per-call | Exam tests that a budget EXISTS, not the specific number | sa-hb1 |
| State storage | SQLite | Queryable, persistent, multi-turn | sa-hb1 |
| Mock backend | 12 orders, 4 customers, 8 edge cases | One edge case per error category × scenario | sa-hb1 |
| Session isolation | Separate agent for review (no builder context) | Domain 4.6: same session is less effective at reviewing its own code | sa-2rm |

---

## Dev Cycle Observations (Process, not just code)

### What the GC dispatch cycle looked like

1. **Sling bead** → `gc sling support-agent/claude sa-hb1` (worked: bead labeled, wisp attached, auto-convoy created)
2. **Session spawn** → GC spawned session `jsc-9qk` (worked: reconciler detected pool work)
3. **Session DIED** → `--dangerously-skip-permissions` blocked as root (infrastructure blocker)
4. **Workaround** → Agent subagent used instead (same session isolation, different dispatch)

**GC friction points from this cycle:**
- Dolt rejects digit-prefix database names → renamed `01-support-agent` to `support-agent`
- Root user + `--dangerously-skip-permissions` = dead sessions
- API key placeholder in factory image = non-interactive sessions can't auth

### What the build-review-iterate cycle looked like

1. **Build** (sa-hb1): Agent subagent built entire app in ~5 minutes
2. **Review** (sa-2rm): Independent reviewer (no builder context) found 3 minor issues, gave grade A
3. **Iterate** (sa-e2p): Third agent (no context from builder or reviewer) fixing the 3 issues

This exercises **three distinct CCA-F patterns:**
- Builder → autonomous execution (Domain 1.1 agentic loop)
- Reviewer → session isolation (Domain 4.6)
- Iterator → iterative refinement from specific feedback (Domain 3.5, 4.4)

---

## What I'd Say in an Interview About This

"The most important lesson from this scenario is that **programmatic enforcement beats prompt instructions for anything with financial consequences.** The exam will give you four choices: enhance the prompt, add few-shot examples, build a routing classifier, or add a programmatic prerequisite. The answer is always the prerequisite when the business rule requires guaranteed compliance.

The second lesson is about **tool descriptions as the primary selection mechanism.** When two tools overlap ('get customer info' vs 'get order info'), the fix isn't a routing layer — it's better descriptions. The five-part discipline (what, inputs, outputs, when to use, when NOT to use) with explicit cross-references is what the exam rewards.

The third lesson is about **escalation triggers.** The exam explicitly marks self-reported confidence as unreliable. The valid triggers are: customer requests it, policy gap, and inability to make progress. Sentiment-based escalation is also invalid — frustration doesn't correlate with case complexity.

On the process side: session isolation between generator and reviewer is a real pattern, not just an exam concept. The reviewer caught issues the builder couldn't see because it had no context about implementation decisions. This maps to Domain 4.6's insight that a model retains reasoning context from generation, making it less likely to question its own decisions."
