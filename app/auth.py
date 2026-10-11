"""JWT authentication with a JSON file-backed user store (no database required)."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import secrets
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

ROLES = {"admin", "faculty", "placement_officer", "judge_demo"}
DEFAULT_SECRET_WARNING = "development-only-insecure-secret-change-before-deployment"
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", DEFAULT_SECRET_WARNING)
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = max(5, min(int(os.getenv("ACCESS_TOKEN_MINUTES", "30")), 1440))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
USERS_FILE = Path(os.getenv("AUTH_USERS_FILE", str(PROJECT_ROOT / "data" / "users.json")))
if not USERS_FILE.is_absolute():
    USERS_FILE = PROJECT_ROOT / USERS_FILE
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
_users_lock = threading.RLock()
logger = logging.getLogger("smart_campus.auth")


def _read_users() -> dict[str, dict]:
    if not USERS_FILE.exists():
        return {}
    try:
        with USERS_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read authentication user file '{USERS_FILE}'.") from exc


def _write_users(users: dict[str, dict]) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(USERS_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(users, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_path, USERS_FILE)
        try:
            USERS_FILE.chmod(0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def init_auth_store() -> None:
    """Create the first administrator once; never overwrite an existing password silently."""
    username = os.getenv("AUTH_BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.getenv("AUTH_BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or not password or len(password) < 12 or "REPLACE_WITH" in password.upper():
        logger.warning("No bootstrap administrator created. Configure AUTH_BOOTSTRAP_ADMIN_USERNAME and a unique AUTH_BOOTSTRAP_ADMIN_PASSWORD (12+ characters) in .env.")
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not USERS_FILE.exists():
            _write_users({})
        return
    with _users_lock:
        users = _read_users()
        if username not in users:
            users[username] = {
                "username": username,
                "password_hash": _hash_password(password),
                "role": "admin",
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            _write_users(users)
            logger.info("Created bootstrap administrator '%s' in the JSON user store.", username)


def create_user(username: str, password: str, role: str) -> dict:
    username = username.strip()
    if not 3 <= len(username) <= 64 or not username.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Username must be 3-64 characters and contain only letters, numbers, '_' or '-'.")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(sorted(ROLES))}.")
    with _users_lock:
        users = _read_users()
        if username in users:
            raise ValueError("That username already exists.")
        users[username] = {"username": username, "password_hash": _hash_password(password),
                           "role": role, "active": True,
                           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        _write_users(users)
    return {"username": username, "role": role, "active": True}


def authenticate_user(username: str, password: str) -> dict | None:
    with _users_lock:
        row = _read_users().get(username.strip())
    if row is None:
        _hash_password(password)
        return None
    if not row.get("active", False) or not _verify_password(password, row.get("password_hash", "")):
        return None
    return {"username": row["username"], "role": row["role"]}


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = _b64decode(salt_text)
        expected = _b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(user: dict) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user["username"], "role": user["role"],
               "iat": int(now.timestamp()), "exp": int(expires.timestamp())}
    head = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{head}.{body}".encode("ascii")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{head}.{body}.{_b64encode(signature)}", ACCESS_TOKEN_MINUTES * 60


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": "Authentication required. Sign in to continue."},
        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise unauthorized
    try:
        head, body, signature = token.split(".", 2)
        header = json.loads(_b64decode(head))
        payload = json.loads(_b64decode(body))
        if not isinstance(header, dict) or not isinstance(payload, dict) or header.get("alg") != "HS256":
            raise unauthorized
        expected = hmac.new(SECRET_KEY.encode("utf-8"), f"{head}.{body}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise unauthorized
        username, role, expires = payload.get("sub"), payload.get("role"), payload.get("exp")
        if not username or role not in ROLES or not isinstance(expires, (int, float)) or expires <= datetime.now(timezone.utc).timestamp():
            raise unauthorized
    except (ValueError, TypeError, KeyError, AttributeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise unauthorized
    with _users_lock:
        row = _read_users().get(username)
    if row is None or not row.get("active", False) or row.get("role") != role:
        raise unauthorized
    return {"username": row["username"], "role": row["role"]}


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail={"message": "Your account does not have permission for this action."})
        return user
    return dependency
