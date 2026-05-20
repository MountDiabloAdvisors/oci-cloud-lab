#!/usr/bin/env python3
"""
Generate ADMIN_PASSWORD_HASH for .env.

Usage:
    python admin/hash_password.py
    python admin/hash_password.py <password>   # non-interactive
"""

from __future__ import annotations

import getpass
import hashlib
import secrets
import sys


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"sha256:260000:{salt}:{h}"


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Admin password: ")
        confirm  = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            raise SystemExit(1)

    if not password:
        print("Password cannot be empty.")
        raise SystemExit(1)

    result = hash_password(password)
    print(f"\nAdd this line to your .env:\n")
    print(f"ADMIN_PASSWORD_HASH={result}")


if __name__ == "__main__":
    main()
