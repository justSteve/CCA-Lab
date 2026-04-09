"""CLI entry point for the customer support agent.

Supports two modes:
1. Single message: ./run.sh "I want to cancel order #1234"
2. Interactive multi-turn: ./run.sh --interactive [--conversation-id ID]

Logs to ./logs/ directory with structured output.
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from src.state import ConversationState, init_state_db, save_state, load_state
from src.agent import run_agent_turn
from src.backend import reset_transient_tracker


def setup_logging():
    """Configure logging to both file and stderr."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log")

    # File handler: DEBUG level, full detail
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    # Stderr handler: WARNING and above only (keep terminal clean for customer output)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root_logger = logging.getLogger("support-agent")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stderr_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    return log_file


def main():
    parser = argparse.ArgumentParser(
        description="Customer Support Resolution Agent",
        epilog="Examples:\n"
               "  ./run.sh \"I want to cancel order #ORD-1001\"\n"
               "  ./run.sh --interactive\n"
               "  ./run.sh --interactive --conversation-id abc123\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("message", nargs="?", help="Customer message (single-turn mode)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive multi-turn session")
    parser.add_argument("--conversation-id", "-c", help="Resume an existing conversation by ID")
    parser.add_argument("--customer-id", help="Pre-set customer ID (e.g., for testing)")

    args = parser.parse_args()

    if not args.message and not args.interactive:
        parser.print_help()
        sys.exit(1)

    log_file = setup_logging()
    logger = logging.getLogger("support-agent.cli")
    logger.info("Session started. Log file: %s", log_file)

    # Initialize state database
    init_state_db()

    # Seed backend if not already done
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backend.db")
    if not os.path.exists(db_path):
        logger.info("Backend database not found; seeding...")
        from data.seed import seed
        seed()

    # Load or create conversation state
    state = None
    if args.conversation_id:
        state = load_state(args.conversation_id)
        if state:
            logger.info("Resumed conversation: %s", state.conversation_id)
        else:
            logger.warning("Conversation %s not found, starting new", args.conversation_id)

    if not state:
        state = ConversationState()
        logger.info("New conversation: %s", state.conversation_id)

    # Reset transient failure simulation for fresh session
    reset_transient_tracker()

    if args.interactive:
        _run_interactive(state, logger)
    else:
        response = run_agent_turn(args.message, state)
        print(f"\n{response}")
        print(f"\n[Conversation ID: {state.conversation_id}]")


def _run_interactive(state: ConversationState, logger):
    """Run an interactive multi-turn conversation loop."""
    print("=" * 60)
    print("Customer Support Agent (Interactive Mode)")
    print(f"Conversation ID: {state.conversation_id}")
    print("Type 'quit' or 'exit' to end the session.")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("\nSession ended. Goodbye!")
            break

        response = run_agent_turn(user_input, state)
        print(f"\nAgent: {response}")

        if state.escalated:
            print("\n[Case has been escalated to a human agent.]")
            break

    print(f"\n[Conversation ID: {state.conversation_id}]")


if __name__ == "__main__":
    main()
