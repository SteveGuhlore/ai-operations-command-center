#!/usr/bin/env python3
"""Test IMAP configuration - diagnostic script"""

import os
import sys
from pathlib import Path

print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path[0]}")

# Find the actual .env file location
env_paths = [
    Path(".env"),
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent.parent.parent / ".env",
]

for p in env_paths:
    print(f"Checking: {p} | exists: {p.exists()}")

# Try loading with explicit path
from dotenv import load_dotenv

base_dir = Path(__file__).parent.parent
env_path = base_dir / ".env"
print(f"\nLoading from: {env_path}")
load_result = load_dotenv(env_path, verbose=True)
print(f"load_dotenv returned: {load_result}")

print("\n=== IMAP Configuration Test ===\n")

# Check what values we're reading
imap_host = os.environ.get("IMAP_HOST")
imap_port = os.environ.get("IMAP_PORT")
imap_user = os.environ.get("IMAP_USER")
imap_password = os.environ.get("IMAP_PASSWORD")

if imap_password:
    imap_password_masked = imap_password[:4] + "****" + imap_password[-4:] if len(imap_password) > 8 else "****"
else:
    imap_password_masked = None

print(f"IMAP_HOST: {imap_host}")
print(f"IMAP_PORT: {imap_port}")
print(f"IMAP_USER: {imap_user}")
print(f"IMAP_PASSWORD set: {bool(imap_password)}")
print(f"IMAP_PASSWORD preview: {imap_password_masked}")

# Check if all required values are present
if not all([imap_host, imap_port, imap_user, imap_password]):
    print("\n❌ ERROR: Missing required IMAP configuration!")
else:
    print("\n✅ IMAP configuration looks complete!")
