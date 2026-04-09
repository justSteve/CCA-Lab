"""Single-agent loop for customer support resolution.

Architecture:
- Takes a customer message
- Decides which tool to call (via Claude)
- Calls the tool, evaluates the result
- Either resolves, asks a clarifying question, or escalates

Error handling by category:
- transient: retry with backoff (up to 3 retries, then escalate)
- validation: surface to model for fix-and-resubmit
- business: surface to customer with explanation
- permission: escalate immediately

This is a single-agent design (not multi-agent). The agent loop runs until
the model produces a final text response or escalates.
"""

import json
import logging
import time
import os
from anthropic import Anthropic

from src.tools import TOOL_DEFINITIONS, execute_tool
from src.state import ConversationState, save_state

logger = logging.getLogger("support-agent.agent")

SYSTEM_PROMPT = """You are a customer support agent for an e-commerce company. Your job is to help customers with order inquiries, refunds, and other support requests.

WORKFLOW:
1. Always verify the customer's identity first using get_customer (by ID or email).
2. Then look up relevant orders using lookup_order.
3. Take action (process_refund) or provide information based on what you find.
4. Escalate to a human agent ONLY when appropriate (see below).

TOOL USAGE RULES:
- You MUST call get_customer before calling process_refund. This is a hard prerequisite.
- When looking up orders, pass the verified customer_id as requesting_customer_id for ownership verification.
- Read tool error responses carefully. Each error has a category and remediation guidance.

ERROR HANDLING:
- If a tool returns a TRANSIENT error (network timeout): retry the same call. You have a budget of 3 retries.
- If a tool returns a VALIDATION error: fix the input and try again.
- If a tool returns a BUSINESS error: explain the situation to the customer clearly.
- If a tool returns a PERMISSION error: do NOT reveal the order details. Tell the customer you cannot access that order.

ESCALATION RULES (strict):
Use escalate_to_human ONLY for these three reasons:
1. The customer explicitly asks to speak with a human representative.
2. A policy exception is needed (e.g., refund over $500 requires human approval, return outside window with compelling reason).
3. You cannot make meaningful progress (e.g., repeated transient failures after retries).

Do NOT escalate based on:
- How long the conversation has been going
- Your own confidence level
- Perceived customer frustration

When escalating, provide a complete handoff: who the customer is, what they wanted, what you tried, what failed, and what the human should do.

TONE:
- Professional, empathetic, concise
- Acknowledge the customer's issue before diving into solutions
- Be transparent about limitations (e.g., "I can't process refunds over $500 automatically")
"""


def run_agent_turn(user_message: str, state: ConversationState) -> str:
    """Run one turn of the agent loop.

    Takes a user message, runs the Claude API loop (potentially multiple
    tool calls), and returns the final text response.

    Args:
        user_message: The customer's message.
        state: Current conversation state.

    Returns:
        The agent's text response to the customer.
    """
    client = Anthropic()

    # Add user message to conversation history
    state.messages.append({"role": "user", "content": user_message})
    state.turn_count += 1

    messages = list(state.messages)
    max_iterations = 15  # Safety limit on tool-call loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info("Agent loop iteration %d (turn %d)", iteration, state.turn_count)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except Exception as e:
            logger.error("Anthropic API error: %s", e)
            error_msg = "I'm sorry, I'm experiencing a technical issue. Please try again in a moment."
            state.messages.append({"role": "assistant", "content": error_msg})
            save_state(state)
            return error_msg

        logger.info("API response: stop_reason=%s, content_blocks=%d",
                     response.stop_reason, len(response.content))

        # Process the response content blocks
        assistant_content = []
        text_parts = []
        tool_use_blocks = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Add assistant message to conversation
        messages.append({"role": "assistant", "content": assistant_content})

        # If stop reason is end_turn or no tool calls, we're done
        if response.stop_reason == "end_turn" or not tool_use_blocks:
            final_text = "\n".join(text_parts) if text_parts else "I'm not sure how to help with that. Could you please provide more details?"
            state.messages.append({"role": "assistant", "content": final_text})
            save_state(state)
            return final_text

        # Process tool calls
        tool_results = []
        for tool_block in tool_use_blocks:
            result_str = _execute_with_retry(tool_block.name, tool_block.input, state)
            result_data = json.loads(result_str)

            # Record for heuristic tracking
            state.record_tool_call(tool_block.name, result_data)

            # Check if retry budget is exhausted -> force escalation
            if state.retry_budget_exhausted and result_data.get("error") and result_data.get("category") == "transient":
                logger.warning("Retry budget exhausted. Forcing escalation.")
                escalation_result = execute_tool("escalate_to_human", {
                    "reason": "progress_blocked",
                    "customer_id": state.verified_customer_id,
                    "attempts_summary": f"Transient failures exhausted retry budget ({state.MAX_TRANSIENT_RETRIES} retries). Last error: {result_data.get('message')}",
                    "recommended_action": "Retry the operation from a human agent dashboard with direct backend access.",
                }, state)
                result_str = escalation_result

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    # Safety: hit max iterations
    logger.error("Hit max iterations (%d) in agent loop", max_iterations)
    fallback = "I apologize, but I'm having difficulty resolving your request. Let me connect you with a human agent who can help."
    state.messages.append({"role": "assistant", "content": fallback})
    save_state(state)
    return fallback


def _execute_with_retry(tool_name: str, arguments: dict, state: ConversationState) -> str:
    """Execute a tool, retrying on transient errors up to the budget.

    Returns the final result string (either success or the last error).
    """
    result_str = execute_tool(tool_name, arguments, state)
    result_data = json.loads(result_str)

    # Auto-retry transient errors within budget
    retries = 0
    while (result_data.get("error")
           and result_data.get("category") == "transient"
           and not state.retry_budget_exhausted
           and retries < 2):  # Max 2 auto-retries per individual call
        retries += 1
        wait = 0.5 * retries  # Simple backoff
        logger.info("Retrying %s after transient error (attempt %d, wait %.1fs)", tool_name, retries, wait)
        time.sleep(wait)

        result_str = execute_tool(tool_name, arguments, state)
        result_data = json.loads(result_str)

    return result_str
