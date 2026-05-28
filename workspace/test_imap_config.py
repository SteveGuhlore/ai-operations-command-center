#!/usr/bin/env python3
"""Test IMAP configuration - diagnostic script"""

import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

print("=== IMAP Configuration Test ===\n")

# Check what values we're reading
imap_host = os.environ.get("IMAP_HOST")
imap_port = os.environ.get("IMAP_PORT")
imap_user = os.environ.get("IMAP_USER")
imap_password = os.environ.get("IMAP_PASSWORD", "")[:4] + "****" if os.environ.get("IMAP_PASSWORD") else None

print(f"IMAP_HOST: {imap_host}")
print(f"IMAP_PORT: {imap_port}")
print(f"IMAP_USER: {imap_user}")
print(f"IMAP_PASSWORD: {imap_password}")
print()

# Test the read_inbox function
from runner.tools.inbox_reader import read_inbox

result = read_inbox(max_messages=5, unread_only=True)
print("\n=== read_inbox() Result ===")
print(f"Error: {result.get('error', 'None')}")
print(f"Messages found: {result.get('total', 0)}")
print(f"Interested count: {result.get('interested_count', 0)}")
