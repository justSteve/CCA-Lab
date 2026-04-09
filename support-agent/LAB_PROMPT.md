# PROMPT 1 — Scenario 1: Customer Support Resolution Agent

> Assumes Prompt 0 (orientation) has been processed. Work happens in `/root/projects/cca-lab/01-support-agent/`.

---

## The assignment

The employer wants an AI customer support agent that handles customer inquiries about orders, resolves common issues directly, and escalates complex cases to human reps with enough context for them to act without re-asking the customer everything. Think of it as the first-line agent for an e-commerce support queue.

The "customer" and the "support backend" are mocked locally — no real e-commerce system, no real ticketing platform — but the architecture should be the architecture you'd use if they were real. The mocks exist so we can iterate quickly and exercise edge cases without standing up infrastructure.

## My intent

A single-agent loop (not multi-agent — that's Scenario 3) that takes a customer message, decides which tool to call, calls it, evaluates the result, and either resolves the case, asks the customer a clarifying question, or escalates to a human with a structured handoff packet. The agent should run from a CLI entry point I can pipe text into and should handle a multi-turn conversation, not just one-shot.

The mock backend is a small JSON file or SQLite database with maybe a dozen orders, a handful of customers, and some realistic edge cases: an order that was refunded last week, an order that shipped this morning and can't be cancelled, an order belonging to a different customer than the one asking, a refund request over a policy threshold. The edge cases exist *because* the exam's wrong-answer traps are exactly those edge cases — the agent that handles them well is the agent that's internalized the exam's lessons.

## What I want built into it deliberately

These are the exam-tested patterns for this scenario. Each one should be present somewhere in the working code so I can read it back later:

1. **Sharply-scoped tools, not one mega-tool.** Don't build a single `manage_order` tool that takes an action parameter. Build separate tools: `lookup_order`, `lookup_customer`, `cancel_order`, `issue_refund`, `escalate_to_human`. Each with the description discipline from the lab conventions: what, inputs, outputs, when to use, when NOT to use. I want to see tool-splitting practiced.

2. **Disambiguation between similar tools.** Make `lookup_order` and `lookup_customer` deliberately tempting to confuse — both retrieve "entity information." Then write descriptions sharp enough that the agent reliably picks the right one. The exam's most-cited tool-design trap is exactly this misrouting case, and I want to feel why descriptions are the fix.

3. **All four error categories represented.** Transient (the mock backend simulates a flaky network with a deliberate fail-then-succeed pattern), validation (an order ID with the wrong format), business (trying to cancel an already-shipped order), permission (a customer asking about another customer's order). Each error returns in the standard envelope (`category`, `message`, `remediation`). The agent's loop handles each category differently: retry transient with backoff, fix-and-resubmit validation, surface business errors to the customer, escalate permission errors.

4. **Three valid escalation triggers, none of the invalid ones.** The agent escalates when: (a) its own confidence is low, (b) it has exhausted retry budget on a recoverable failure, or (c) the request matches a policy condition (e.g., refund amount over a threshold). It does NOT escalate based on conversation duration or inferred user frustration. Enforce this in code, not just in comments.

5. **Context summarization for handoff, not progressive in-conversation summarization.** When the agent escalates, it produces a structured handoff packet for the human: customer identity, the original request, what the agent tried, what failed and why, what context the human needs to know. This is summarization done right. What the agent should NOT do is summarize the conversation periodically as it grows — that's the progressive-summarization anti-pattern. The conversation stays in full fidelity until the moment of handoff.

## Specific things to ask me before starting

Don't guess on these. Surface them as questions:

- Confidence scoring for the escalation trigger — should we rely on the model self-reporting confidence, use a separate evaluator call, or use a heuristic based on tool-call patterns? Each has trade-offs and I want you to walk me through them before picking.
- Retry budget — how many transient retries before escalating? The exam doesn't give a magic number; it tests that you have a budget at all.
- Multi-turn state — store conversation in memory only, in a local SQLite, or in JSON files per conversation? I lean SQLite for anything I might want to query later, but you tell me what fits.
- Mock backend shape — generate the fixtures yourself based on the edge cases above, or do you want me to provide them? I'm fine either way; generated is faster.

## Done means

I should be able to do this:

```
cd /root/projects/cca-lab/01-support-agent
./run.sh "I want to cancel order #1234"
./run.sh "Why hasn't my refund arrived?"
./run.sh "Can you tell me the status of order #9999?"   # belongs to another customer
./run.sh "I need to return an item I bought 6 months ago"  # business rule violation
```

…and watch the agent route correctly, hit the right error categories, and escalate when (and only when) it should. The escalation handoff packet should be human-readable and complete enough that I, playing the human reviewer, would know exactly what to do next.

After it works, write NOTES.md in the scenario directory mapping the exam concepts each part of the code demonstrates. That's the artifact I'll re-read on exam day.

## What I'm NOT asking for

This is a single-agent scenario. Do not introduce subagents, hub-and-spoke, or any multi-agent coordination — that's Scenario 3 and I want the contrast to be clean. Do not over-engineer the mock backend — it's fixtures, not a real system. Do not skip the clarifying-question step at the start, even if you think you know what I want.
