"""Mock backend — SQLite queries with simulated failure modes.

This module simulates a real backend service. It includes:
- Transient failures (flaky network simulation)
- Validation checks (ID format)
- Business rule enforcement (shipped orders, return windows, refund thresholds)
- Permission checks (customer ownership)
"""

import sqlite3
import os
import json
import random
import logging
from datetime import datetime, timedelta, timezone

from src.errors import error_envelope, success_envelope

logger = logging.getLogger("support-agent.backend")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backend.db")

# Policy constants
REFUND_THRESHOLD = 500.00  # Refunds above this require human approval
RETURN_WINDOW_DAYS = 90    # Orders older than this cannot be returned

# Transient failure simulation: ~30% chance on first call per "session"
# We track call counts to simulate fail-then-succeed pattern
_transient_failure_tracker: dict[str, int] = {}


def _maybe_transient_fail(operation: str) -> dict | None:
    """Simulate a flaky network. First call to an operation has a 30% fail chance.
    Second call always succeeds (fail-then-succeed pattern for retry testing)."""
    key = operation
    count = _transient_failure_tracker.get(key, 0)
    _transient_failure_tracker[key] = count + 1

    if count == 0 and random.random() < 0.30:
        logger.warning("Transient failure simulated for operation=%s", operation)
        return error_envelope(
            category="transient",
            message=f"Connection timeout while executing {operation}. The backend service did not respond within 5s.",
            remediation="Retry the request. This is a transient network issue.",
            is_retryable=True,
        )
    return None


def reset_transient_tracker():
    """Reset transient failure tracking (useful between conversations)."""
    _transient_failure_tracker.clear()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_customer(customer_id: str = None, email: str = None) -> dict:
    """Look up a customer by ID or email.

    Returns success envelope with customer data, or appropriate error envelope.
    A query that finds no match returns a successful empty result (not an error).
    """
    # Transient simulation
    fail = _maybe_transient_fail("get_customer")
    if fail:
        return fail

    # Validation
    if not customer_id and not email:
        return error_envelope(
            category="validation",
            message="Either customer_id or email must be provided.",
            remediation="Supply a valid customer_id (format: CUST-XXX) or email address.",
            is_retryable=False,
        )

    if customer_id and not customer_id.startswith("CUST-"):
        return error_envelope(
            category="validation",
            message=f"Invalid customer ID format: '{customer_id}'. Expected format: CUST-XXX.",
            remediation="Provide a customer ID in the format CUST-XXX (e.g., CUST-001).",
            is_retryable=False,
        )

    conn = _get_conn()
    try:
        if customer_id:
            row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()

        if not row:
            # Valid empty result -- not an error (Domain 2.2 distinction)
            logger.info("Customer lookup returned no results: id=%s email=%s", customer_id, email)
            return success_envelope({"customer": None, "message": "No customer found matching the provided criteria."})

        customer = {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "created_at": row["created_at"],
        }
        logger.info("Customer found: %s", customer["id"])
        return success_envelope({"customer": customer})
    finally:
        conn.close()


def lookup_order(order_id: str, requesting_customer_id: str = None) -> dict:
    """Look up an order by order ID.

    If requesting_customer_id is provided, enforces ownership check.
    """
    # Transient simulation
    fail = _maybe_transient_fail(f"lookup_order_{order_id}")
    if fail:
        return fail

    # Validation
    if not order_id or not order_id.startswith("ORD-"):
        return error_envelope(
            category="validation",
            message=f"Invalid order ID format: '{order_id}'. Expected format: ORD-XXXX.",
            remediation="Provide an order ID in the format ORD-XXXX (e.g., ORD-1001).",
            is_retryable=False,
        )

    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

        if not row:
            # Valid empty result
            logger.info("Order lookup returned no results: %s", order_id)
            return success_envelope({"order": None, "message": f"No order found with ID {order_id}."})

        # Permission check: if we know who's asking, verify ownership
        if requesting_customer_id and row["customer_id"] != requesting_customer_id:
            logger.warning(
                "Permission denied: customer %s attempted to access order %s owned by %s",
                requesting_customer_id, order_id, row["customer_id"],
            )
            return error_envelope(
                category="permission",
                message=f"Order {order_id} does not belong to customer {requesting_customer_id}.",
                remediation="This order belongs to a different customer. The agent cannot disclose details. Escalate if the customer insists.",
                is_retryable=False,
            )

        order = {
            "id": row["id"],
            "customer_id": row["customer_id"],
            "status": row["status"],
            "total": row["total"],
            "items": json.loads(row["items"]),
            "created_at": row["created_at"],
            "shipped_at": row["shipped_at"],
            "refunded_at": row["refunded_at"],
            "refund_amount": row["refund_amount"],
        }
        logger.info("Order found: %s (status=%s)", order["id"], order["status"])
        return success_envelope({"order": order})
    finally:
        conn.close()


def process_refund(order_id: str, requesting_customer_id: str, reason: str = "") -> dict:
    """Process a refund for an order.

    Business rules enforced:
    - Order must exist and belong to the requesting customer
    - Order must be in a refundable state (delivered, not already refunded)
    - Order must be within the return window
    - Refunds over the threshold require human approval (escalation)
    """
    # Transient simulation
    fail = _maybe_transient_fail(f"process_refund_{order_id}")
    if fail:
        return fail

    # Validation
    if not order_id or not order_id.startswith("ORD-"):
        return error_envelope(
            category="validation",
            message=f"Invalid order ID format: '{order_id}'.",
            remediation="Provide an order ID in the format ORD-XXXX.",
            is_retryable=False,
        )

    if not requesting_customer_id:
        return error_envelope(
            category="validation",
            message="Customer ID is required to process a refund.",
            remediation="Look up the customer first using get_customer, then provide their verified ID.",
            is_retryable=False,
        )

    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

        if not row:
            return success_envelope({"refund": None, "message": f"No order found with ID {order_id}."})

        # Permission check
        if row["customer_id"] != requesting_customer_id:
            return error_envelope(
                category="permission",
                message=f"Order {order_id} does not belong to customer {requesting_customer_id}.",
                remediation="Cannot process refund for another customer's order. Escalate if needed.",
                is_retryable=False,
            )

        # Business rules
        if row["status"] == "refunded":
            return error_envelope(
                category="business",
                message=f"Order {order_id} was already refunded on {row['refunded_at']}.",
                remediation="Inform the customer that a refund has already been processed for this order.",
                is_retryable=False,
            )

        if row["status"] == "cancelled":
            return error_envelope(
                category="business",
                message=f"Order {order_id} is cancelled and cannot be refunded.",
                remediation="Cancelled orders were never charged. No refund is needed.",
                is_retryable=False,
            )

        if row["status"] in ("pending", "processing"):
            return error_envelope(
                category="business",
                message=f"Order {order_id} has not shipped yet (status: {row['status']}). Cancel instead of refunding.",
                remediation="Use order cancellation for orders that haven't shipped. Refunds apply to delivered orders.",
                is_retryable=False,
            )

        if row["status"] == "shipped":
            return error_envelope(
                category="business",
                message=f"Order {order_id} is currently in transit. Cannot refund until delivered.",
                remediation="The customer must wait for delivery before requesting a refund, or refuse delivery.",
                is_retryable=False,
            )

        # Check return window
        created = datetime.fromisoformat(row["created_at"])
        if (datetime.now(timezone.utc) - created).days > RETURN_WINDOW_DAYS:
            return error_envelope(
                category="business",
                message=f"Order {order_id} is outside the {RETURN_WINDOW_DAYS}-day return window (ordered {created.date()}).",
                remediation="The return window has expired. Escalate if the customer has a compelling reason for an exception.",
                is_retryable=False,
            )

        # Check refund threshold -- policy exception triggers escalation
        if row["total"] > REFUND_THRESHOLD:
            return error_envelope(
                category="business",
                message=f"Refund amount ${row['total']:.2f} exceeds the ${REFUND_THRESHOLD:.2f} auto-approval threshold.",
                remediation="This refund requires human approval. Escalate to a human agent with the refund details.",
                is_retryable=False,
            )

        # Process the refund
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE orders SET status = 'refunded', refunded_at = ?, refund_amount = ? WHERE id = ?",
            (now, row["total"], order_id),
        )
        conn.commit()

        logger.info("Refund processed: order=%s amount=%.2f", order_id, row["total"])
        return success_envelope({
            "refund": {
                "order_id": order_id,
                "amount": row["total"],
                "refunded_at": now,
                "status": "refunded",
            },
            "message": f"Refund of ${row['total']:.2f} processed successfully for order {order_id}.",
        })
    finally:
        conn.close()
