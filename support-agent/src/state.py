"""Conversation state management with SQLite persistence.

Maintains full conversation fidelity (no progressive summarization).
Summarization happens only at escalation/handoff time.
"""

import sqlite3
import json
import os
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("support-agent.state")

STATE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "conversations.db")


@dataclass
class ConversationState:
    """Tracks state for a single support conversation.

    This is the in-memory state that the agent loop reads and updates.
    It is persisted to SQLite for queryability.
    """
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    verified_customer_id: str | None = None
    turn_count: int = 0
    tools_called: list = field(default_factory=list)
    transient_retry_count: int = 0
    escalated: bool = False
    messages: list = field(default_factory=list)

    # Retry budget: 3 transient retries before escalation
    MAX_TRANSIENT_RETRIES = 3

    def record_tool_call(self, tool_name: str, result: dict):
        """Record a tool call for heuristic confidence and handoff context."""
        self.tools_called.append(tool_name)

        # Track transient retries
        if result.get("error") and result.get("category") == "transient":
            self.transient_retry_count += 1
            logger.info(
                "Transient retry count: %d/%d",
                self.transient_retry_count, self.MAX_TRANSIENT_RETRIES,
            )

    @property
    def retry_budget_exhausted(self) -> bool:
        return self.transient_retry_count >= self.MAX_TRANSIENT_RETRIES

    @property
    def should_escalate_retries(self) -> bool:
        """Heuristic: escalate if retry budget is exhausted."""
        return self.retry_budget_exhausted


def init_state_db():
    """Create the conversations table if it doesn't exist."""
    os.makedirs(os.path.dirname(STATE_DB), exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            verified_customer_id TEXT,
            turn_count INTEGER DEFAULT 0,
            tools_called TEXT DEFAULT '[]',
            escalated INTEGER DEFAULT 0,
            messages TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()
    logger.debug("State DB initialized at %s", STATE_DB)


def save_state(state: ConversationState):
    """Persist conversation state to SQLite."""
    conn = sqlite3.connect(STATE_DB)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO conversations (id, created_at, updated_at, verified_customer_id,
                                   turn_count, tools_called, escalated, messages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            updated_at = ?,
            verified_customer_id = ?,
            turn_count = ?,
            tools_called = ?,
            escalated = ?,
            messages = ?
    """, (
        state.conversation_id, now, now, state.verified_customer_id,
        state.turn_count, json.dumps(state.tools_called), int(state.escalated),
        json.dumps(state.messages),
        # ON CONFLICT SET values:
        now, state.verified_customer_id, state.turn_count,
        json.dumps(state.tools_called), int(state.escalated),
        json.dumps(state.messages),
    ))
    conn.commit()
    conn.close()


def load_state(conversation_id: str) -> ConversationState | None:
    """Load a conversation state from SQLite, or None if not found."""
    conn = sqlite3.connect(STATE_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    conn.close()

    if not row:
        return None

    state = ConversationState(
        conversation_id=row["id"],
        verified_customer_id=row["verified_customer_id"],
        turn_count=row["turn_count"],
        tools_called=json.loads(row["tools_called"]),
        transient_retry_count=0,  # Reset per session; transient failures are session-scoped
        escalated=bool(row["escalated"]),
        messages=json.loads(row["messages"]),
    )
    return state
