"""Tool definitions for the Anthropic API and tool execution dispatch.

Each tool has a sharply-scoped description following the discipline:
what, inputs, outputs, when to use, when NOT to use.

Programmatic prerequisite enforcement (Domain 1.4):
- process_refund is BLOCKED until get_customer has returned a verified
  customer ID in the current conversation. This is enforced in code via
  the ConversationState.verified_customer_id field.
"""

import json
import logging
from src import backend

logger = logging.getLogger("support-agent.tools")

# -- Tool definitions for Anthropic API --

TOOL_DEFINITIONS = [
    {
        "name": "get_customer",
        "description": (
            "Look up a customer record by customer ID or email address.\n\n"
            "INPUTS: customer_id (string, format CUST-XXX) OR email (string). At least one required.\n"
            "OUTPUTS: Customer record with id, name, email, created_at. "
            "Returns empty result (not an error) if no customer matches.\n\n"
            "WHEN TO USE: At the start of any support interaction to verify the customer's identity. "
            "Use this BEFORE any order lookup or refund operation. "
            "This is a prerequisite for process_refund.\n\n"
            "WHEN NOT TO USE: Do NOT use this to look up order information. "
            "Customer records do not contain order details. Use lookup_order for order data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID in format CUST-XXX (e.g., CUST-001).",
                },
                "email": {
                    "type": "string",
                    "description": "Customer email address.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "lookup_order",
        "description": (
            "Retrieve details for a specific order by its order ID.\n\n"
            "INPUTS: order_id (string, format ORD-XXXX, required). "
            "requesting_customer_id (string, optional but recommended for ownership verification).\n"
            "OUTPUTS: Order record with id, customer_id, status, total, items, dates. "
            "Returns empty result (not an error) if no order matches.\n\n"
            "WHEN TO USE: When a customer asks about a specific order's status, details, or shipment. "
            "Also use before process_refund to check order eligibility.\n\n"
            "WHEN NOT TO USE: Do NOT use this to look up customer identity information. "
            "Orders contain a customer_id reference but not full customer details. "
            "Use get_customer for customer data. "
            "Do NOT use this to search for orders by customer -- it requires a specific order ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID in format ORD-XXXX (e.g., ORD-1001).",
                },
                "requesting_customer_id": {
                    "type": "string",
                    "description": "The verified customer ID of the person requesting. Used for ownership check.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Issue a refund for a delivered order.\n\n"
            "INPUTS: order_id (string, required), requesting_customer_id (string, required), "
            "reason (string, optional).\n"
            "OUTPUTS: Refund confirmation with amount and timestamp, or error with category.\n\n"
            "PREREQUISITE: get_customer MUST have been called and returned a verified customer ID "
            "in this conversation BEFORE calling process_refund. This is enforced programmatically.\n\n"
            "WHEN TO USE: When a customer requests a refund for a delivered order that is within "
            "the 90-day return window and under the $500 auto-approval threshold.\n\n"
            "WHEN NOT TO USE: Do NOT use for orders that haven't been delivered yet (use cancellation instead). "
            "Do NOT use if the customer has not been verified via get_customer. "
            "Do NOT use for refunds over $500 -- those require human approval via escalate_to_human."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID to refund (format ORD-XXXX).",
                },
                "requesting_customer_id": {
                    "type": "string",
                    "description": "Verified customer ID from a prior get_customer call.",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the refund request.",
                },
            },
            "required": ["order_id", "requesting_customer_id"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate the current support case to a human agent with a structured handoff packet.\n\n"
            "INPUTS: reason (string, required), customer_id (string), order_id (string), "
            "attempts_summary (string), recommended_action (string).\n"
            "OUTPUTS: Confirmation that escalation was created with a ticket ID.\n\n"
            "WHEN TO USE: Only for these three valid triggers:\n"
            "1. Customer explicitly requests to speak with a human.\n"
            "2. A policy exception or gap is encountered (e.g., refund over $500 threshold).\n"
            "3. The agent cannot make meaningful progress (e.g., retry budget exhausted after 3 transient failures).\n\n"
            "WHEN NOT TO USE: Do NOT escalate based on conversation length or duration. "
            "Do NOT escalate based on inferred customer frustration or sentiment. "
            "Do NOT escalate based on model self-reported confidence scores. "
            "These are explicitly invalid escalation triggers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why escalation is needed. Must map to one of: 'customer_requested', 'policy_exception', 'progress_blocked'.",
                },
                "customer_id": {
                    "type": "string",
                    "description": "Verified customer ID, if available.",
                },
                "order_id": {
                    "type": "string",
                    "description": "Related order ID, if applicable.",
                },
                "attempts_summary": {
                    "type": "string",
                    "description": "Summary of what the agent tried and what failed.",
                },
                "recommended_action": {
                    "type": "string",
                    "description": "What the human agent should do next.",
                },
            },
            "required": ["reason"],
        },
    },
]


def execute_tool(name: str, arguments: dict, conversation_state: "ConversationState") -> str:
    """Execute a tool call and return the JSON result string.

    Enforces programmatic prerequisites:
    - process_refund requires verified_customer_id in conversation state.

    Args:
        name: Tool name.
        arguments: Tool arguments dict.
        conversation_state: Current conversation state for prerequisite checks.

    Returns:
        JSON string of the tool result.
    """
    logger.info("Executing tool: %s with args: %s", name, json.dumps(arguments))

    if name == "get_customer":
        result = backend.get_customer(
            customer_id=arguments.get("customer_id"),
            email=arguments.get("email"),
        )
        # Track verified customer for prerequisite enforcement
        if not result.get("error") and result.get("data", {}).get("customer"):
            conversation_state.verified_customer_id = result["data"]["customer"]["id"]
            logger.info("Customer verified: %s", conversation_state.verified_customer_id)
        return json.dumps(result)

    elif name == "lookup_order":
        result = backend.lookup_order(
            order_id=arguments.get("order_id", ""),
            requesting_customer_id=arguments.get("requesting_customer_id"),
        )
        return json.dumps(result)

    elif name == "process_refund":
        # PROGRAMMATIC PREREQUISITE (Domain 1.4):
        # Block process_refund unless get_customer has returned a verified ID
        if not conversation_state.verified_customer_id:
            logger.warning("process_refund blocked: no verified customer ID in conversation")
            from src.errors import error_envelope
            result = error_envelope(
                category="validation",
                message="Cannot process refund: customer identity has not been verified in this conversation.",
                remediation="Call get_customer first to verify the customer's identity before processing a refund.",
                is_retryable=False,
            )
            return json.dumps(result)

        result = backend.process_refund(
            order_id=arguments.get("order_id", ""),
            requesting_customer_id=arguments.get("requesting_customer_id", ""),
            reason=arguments.get("reason", ""),
        )
        return json.dumps(result)

    elif name == "escalate_to_human":
        # Build structured handoff packet
        handoff = _build_handoff_packet(arguments, conversation_state)
        result = {
            "error": False,
            "data": {
                "escalation": handoff,
                "message": f"Case escalated to human agent. Ticket ID: {handoff['ticket_id']}.",
            },
        }
        conversation_state.escalated = True
        logger.info("Case escalated: ticket=%s reason=%s", handoff["ticket_id"], arguments.get("reason"))
        return json.dumps(result)

    else:
        logger.error("Unknown tool: %s", name)
        return json.dumps({"error": True, "category": "validation", "message": f"Unknown tool: {name}"})


def _build_handoff_packet(arguments: dict, state: "ConversationState") -> dict:
    """Build a structured handoff packet for human agents.

    Context summarization happens here at handoff time (not progressively).
    """
    import hashlib
    import time

    ticket_id = f"ESC-{hashlib.md5(str(time.time()).encode()).hexdigest()[:6].upper()}"

    return {
        "ticket_id": ticket_id,
        "escalation_reason": arguments.get("reason", "unspecified"),
        "customer_id": arguments.get("customer_id") or state.verified_customer_id,
        "order_id": arguments.get("order_id"),
        "attempts_summary": arguments.get("attempts_summary", "No attempts recorded."),
        "recommended_action": arguments.get("recommended_action", "Review case details."),
        "conversation_turn_count": state.turn_count,
        "tools_called": list(state.tools_called),
        "transient_retry_count": state.transient_retry_count,
        "conversation_messages": list(state.messages),
    }
