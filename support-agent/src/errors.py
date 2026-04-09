"""Standardized error envelope for all tool responses.

Every tool error returns this structure so the agent loop can route
errors by category: retry transient, fix-and-resubmit validation,
surface business errors, escalate permission errors.
"""


def error_envelope(category: str, message: str, remediation: str, is_retryable: bool) -> dict:
    """Build a standard error response envelope.

    Args:
        category: One of 'transient', 'validation', 'business', 'permission'.
        message: Human-readable description of what went wrong.
        remediation: Suggested next step for the agent or human.
        is_retryable: Whether the operation can be retried.

    Returns:
        dict with category, message, remediation, isRetryable fields.
    """
    return {
        "error": True,
        "category": category,
        "message": message,
        "remediation": remediation,
        "isRetryable": is_retryable,
    }


def success_envelope(data: dict) -> dict:
    """Wrap a successful result."""
    return {
        "error": False,
        "data": data,
    }
