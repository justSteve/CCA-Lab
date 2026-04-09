# Rig 01 Errata — Lab Prompt vs Official Exam Guide

**Source:** gtOps design spec Appendix A + fresh cross-reference pass

## Corrections to apply during implementation

### Tool names (from Appendix A)

Lab Prompt 1 uses:
- `lookup_order` → **keep** (matches official guide)
- `lookup_customer` → **rename to `get_customer`** (official guide name)
- `cancel_order` → lab-only convenience, not in official guide. Keep but
  note it's not exam-tested.
- `issue_refund` → **rename to `process_refund`** (official guide name)
- `escalate_to_human` → **keep** (matches official guide)

### Escalation triggers (from Appendix A, Domain 5.2)

Lab prompt says escalate on:
1. Low confidence ← **CAUTION**: official guide lists "self-reported
   confidence scores" as **explicitly unreliable** for escalation.
   Do NOT use model self-reported confidence as a trigger. Instead
   use: inability to make meaningful progress (the official framing).
2. Retry budget exhausted ← Maps to official "inability to make
   meaningful progress." **Keep, relabel.**
3. Policy condition (refund over threshold) ← Maps to official "policy
   exceptions/gaps." **Keep, relabel.**

Official guide adds a trigger lab prompt omits:
4. **Customer explicitly requests a human** ← Must be implemented.
   This is a valid trigger in the official guide.

Official guide explicitly marks as **invalid**:
- Sentiment-based escalation (lab prompt correctly excludes this)
- Self-reported confidence scores (lab prompt INCORRECTLY includes this)

### Error categories

Lab prompt's four categories (transient, validation, business, permission)
are not directly from the official guide but are a reasonable
implementation pattern. Keep as-is but note in NOTES.md that this is a
lab convention, not an exam-tested taxonomy.

## Fresh cross-reference items (from full exam guide read)

### Context summarization

Lab prompt correctly specifies: summarize at handoff only, not
progressively during conversation. This aligns with the official guide's
emphasis on maintaining full conversation fidelity (Domain 5.1). No
correction needed.

### Tool description discipline

Lab prompt says: what, inputs, outputs, when to use, when NOT to use.
Official guide emphasizes: "especially against similar tools" — the
disambiguation angle. Lab prompt already covers this with the
`lookup_order` vs `get_customer` deliberate confusion. No correction
needed, but the emphasis on "when NOT to use" should be visible in the
tool descriptions.

### Programmatic prerequisite enforcement (Domain 1.4)

The official exam guide (Task 1.4, Sample Question 1) explicitly tests
**programmatic prerequisites that block downstream tool calls until
prerequisite steps complete** — e.g., blocking `process_refund` until
`get_customer` has returned a verified customer ID. The lab prompt
mentions tool-splitting but doesn't mention this enforcement pattern.
**Should be implemented:** a hook that blocks `process_refund` and
`cancel_order` unless `get_customer` has been called first in the
current conversation.

### Structured error metadata fields (Domain 2.2)

The official guide specifies error responses should include
`errorCategory` (transient/validation/permission), **`isRetryable`
boolean**, and human-readable descriptions. Lab prompt's error envelope
has `category`, `message`, `remediation` but omits `isRetryable`.
**Add `isRetryable` field** to the error envelope.

### Valid empty results vs access failures (Domain 2.2, 5.3)

The guide explicitly tests the distinction: a query that returns no
results is a **successful query** (not an error), while a query that
times out is an **access failure** (an error). The mock backend should
include this scenario: a customer lookup that legitimately finds no
matching customer (return success with empty result, not an error).

### Customer explicitly requests a human (Domain 5.2)

Added above in Escalation Triggers section. This is a **fourth valid
trigger** the lab prompt omits. Must be implemented.
