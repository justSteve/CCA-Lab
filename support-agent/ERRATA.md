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

## Fresh cross-reference items (not in Appendix A)

### Context summarization

Lab prompt correctly specifies: summarize at handoff only, not
progressively during conversation. This aligns with the official guide's
emphasis on maintaining full conversation fidelity. No correction needed.

### Tool description discipline

Lab prompt says: what, inputs, outputs, when to use, when NOT to use.
Official guide emphasizes: "especially against similar tools" — the
disambiguation angle. Lab prompt already covers this with the
`lookup_order` vs `get_customer` deliberate confusion. No correction
needed, but the emphasis on "when NOT to use" should be visible in the
tool descriptions.
