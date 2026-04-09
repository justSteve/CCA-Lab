#!/usr/bin/env python3
"""Seed the mock backend SQLite database with customers, orders, and edge cases."""

import sqlite3
import os
import json
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "backend.db")


def seed():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE customers (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE orders (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            status TEXT NOT NULL,
            total REAL NOT NULL,
            items TEXT NOT NULL,
            created_at TEXT NOT NULL,
            shipped_at TEXT,
            refunded_at TEXT,
            refund_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    now = datetime.now(timezone.utc)

    customers = [
        ("CUST-001", "alice@example.com", "Alice Johnson", (now - timedelta(days=365)).isoformat()),
        ("CUST-002", "bob@example.com", "Bob Smith", (now - timedelta(days=200)).isoformat()),
        ("CUST-003", "carol@example.com", "Carol Davis", (now - timedelta(days=90)).isoformat()),
        ("CUST-004", "dave@example.com", "Dave Wilson", (now - timedelta(days=30)).isoformat()),
    ]

    for cust in customers:
        c.execute("INSERT INTO customers VALUES (?,?,?,?)", cust)

    orders = [
        # Normal pending order - can be cancelled
        ("ORD-1001", "CUST-001", "pending", 49.99,
         json.dumps([{"name": "USB Cable", "qty": 2, "price": 24.995}]),
         (now - timedelta(days=1)).isoformat(), None, None, None),

        # Shipped today - cannot cancel
        ("ORD-1002", "CUST-001", "shipped", 129.99,
         json.dumps([{"name": "Wireless Headphones", "qty": 1, "price": 129.99}]),
         (now - timedelta(days=3)).isoformat(), now.isoformat(), None, None),

        # Delivered - eligible for refund (under threshold)
        ("ORD-1003", "CUST-001", "delivered", 75.00,
         json.dumps([{"name": "Book Set", "qty": 3, "price": 25.00}]),
         (now - timedelta(days=14)).isoformat(), (now - timedelta(days=10)).isoformat(), None, None),

        # Already refunded last week
        ("ORD-1004", "CUST-002", "refunded", 39.99,
         json.dumps([{"name": "Phone Case", "qty": 1, "price": 39.99}]),
         (now - timedelta(days=30)).isoformat(), (now - timedelta(days=25)).isoformat(),
         (now - timedelta(days=7)).isoformat(), 39.99),

        # Bob's order - for permission error testing (wrong customer)
        ("ORD-1005", "CUST-002", "delivered", 199.99,
         json.dumps([{"name": "Smart Watch", "qty": 1, "price": 199.99}]),
         (now - timedelta(days=20)).isoformat(), (now - timedelta(days=16)).isoformat(), None, None),

        # High-value order - refund over $500 threshold triggers escalation
        ("ORD-1006", "CUST-003", "delivered", 899.99,
         json.dumps([{"name": "Laptop Stand", "qty": 1, "price": 149.99},
                      {"name": "Monitor", "qty": 1, "price": 750.00}]),
         (now - timedelta(days=10)).isoformat(), (now - timedelta(days=7)).isoformat(), None, None),

        # Old order - outside return window (180+ days)
        ("ORD-1007", "CUST-003", "delivered", 59.99,
         json.dumps([{"name": "Desk Lamp", "qty": 1, "price": 59.99}]),
         (now - timedelta(days=200)).isoformat(), (now - timedelta(days=195)).isoformat(), None, None),

        # Processing order
        ("ORD-1008", "CUST-002", "processing", 89.50,
         json.dumps([{"name": "Keyboard", "qty": 1, "price": 89.50}]),
         (now - timedelta(hours=6)).isoformat(), None, None, None),

        # Cancelled order
        ("ORD-1009", "CUST-004", "cancelled", 34.99,
         json.dumps([{"name": "Mouse Pad", "qty": 1, "price": 34.99}]),
         (now - timedelta(days=5)).isoformat(), None, None, None),

        # Another pending for Dave
        ("ORD-1010", "CUST-004", "pending", 249.99,
         json.dumps([{"name": "Ergonomic Chair Cushion", "qty": 1, "price": 249.99}]),
         (now - timedelta(hours=2)).isoformat(), None, None, None),

        # Shipped order for Carol
        ("ORD-1011", "CUST-003", "shipped", 159.00,
         json.dumps([{"name": "Backpack", "qty": 1, "price": 159.00}]),
         (now - timedelta(days=2)).isoformat(), (now - timedelta(hours=4)).isoformat(), None, None),

        # Delivered order for Dave - small value
        ("ORD-1012", "CUST-004", "delivered", 12.99,
         json.dumps([{"name": "Sticker Pack", "qty": 1, "price": 12.99}]),
         (now - timedelta(days=15)).isoformat(), (now - timedelta(days=12)).isoformat(), None, None),
    ]

    for order in orders:
        c.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", order)

    conn.commit()
    conn.close()
    print(f"Seeded {len(customers)} customers and {len(orders)} orders into {DB_PATH}")


if __name__ == "__main__":
    seed()
