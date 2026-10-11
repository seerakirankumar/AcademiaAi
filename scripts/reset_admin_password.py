"""Reset or create the local CSV-project administrator account.

Run from the project root with the virtual environment activated:
    python scripts/reset_admin_password.py
"""
from __future__ import annotations

import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.auth import USERS_FILE, _hash_password, _read_users, _write_users  # noqa: E402


def main() -> None:
    username = input("Administrator username: ").strip()
    if not username or not 3 <= len(username) <= 64 or not username.replace("_", "").replace("-", "").isalnum():
        raise SystemExit("Username must be 3-64 characters and contain only letters, numbers, '_' or '-'.")
    password = getpass.getpass("New password (at least 12 characters): ")
    confirm = getpass.getpass("Confirm new password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    users = _read_users()
    existing = users.get(username, {})
    users[username] = {
        "username": username,
        "password_hash": _hash_password(password),
        "role": "admin",
        "active": True,
        "created_at": existing.get("created_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    }
    _write_users(users)
    print(f"Administrator '{username}' is ready. User store: {USERS_FILE}")


if __name__ == "__main__":
    main()
