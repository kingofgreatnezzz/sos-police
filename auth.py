"""
auth.py
=================================================================
Authentication and authorisation module
Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================

Security approach
-----------------
Passwords are **never** stored in plain text.  Each password is hashed
with PBKDF2-HMAC-SHA256 (from Python's built-in ``hashlib``) using a
unique 16-byte random salt and 120 000 iterations, and stored in the
following portable format::

    pbkdf2_sha256$120000$<salt_hex>$<hash_hex>

Comparison uses :func:`hmac.compare_digest` so that verification time
does not leak information about the stored hash (constant-time compare).

An older ``sha256$<salt>$<hash>`` format is still accepted so that a
database created by an earlier prototype keeps working.
"""

from __future__ import annotations

import binascii
import hashlib
import hmac
import os
import re
from typing import Optional

import db

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 120_000
SALT_BYTES = 16

VALID_ROLES = ("Admin", "Viewer")

ROLE_LABELS = {
    "Admin": "Admin / Commander",
    "Viewer": "Viewer / Dispatcher (Read-only)",
}

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


# ---------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------
def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """
    Hash a plain-text password for safe storage.

    Returns a self-describing string:
    ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``
    """
    if password is None or str(password) == "":
        raise ValueError("Password must not be empty.")

    password_bytes = str(password).encode("utf-8")
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, iterations)
    return "{}${}${}${}".format(
        PBKDF2_ALGORITHM,
        iterations,
        binascii.hexlify(salt).decode("ascii"),
        binascii.hexlify(digest).decode("ascii"),
    )


def check_password(password: str, stored_hash: str) -> bool:
    """
    Verify a plain-text password against a stored hash.

    Supports the current ``pbkdf2_sha256`` format and the legacy
    ``sha256$salt$hash`` format.  Never raises on malformed input - it
    simply returns ``False`` so a corrupt row cannot crash a login page.
    """
    if not password or not stored_hash:
        return False

    try:
        parts = str(stored_hash).split("$")

        # ---- Current format: pbkdf2_sha256$iterations$salt$hash
        if len(parts) == 4 and parts[0] == PBKDF2_ALGORITHM:
            _, iterations_text, salt_hex, expected_hex = parts
            iterations = int(iterations_text)
            salt = binascii.unhexlify(salt_hex.encode("ascii"))
            digest = hashlib.pbkdf2_hmac(
                "sha256", str(password).encode("utf-8"), salt, iterations
            )
            return hmac.compare_digest(binascii.hexlify(digest).decode("ascii"), expected_hex)

        # ---- Legacy format: sha256$salt$hash
        if len(parts) == 3 and parts[0] == "sha256":
            _, salt, expected = parts
            digest = hashlib.sha256((salt + str(password)).encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, expected)

        # ---- Bare SHA-256 (very old prototype data)
        if len(parts) == 1 and len(parts[0]) == 64:
            digest = hashlib.sha256(str(password).encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, parts[0])

    except (ValueError, TypeError, binascii.Error):
        return False

    return False


def password_strength(password: str) -> tuple[int, str]:
    """
    Simple strength meter for the "create user" form.

    Returns ``(score 0-4, label)``.
    """
    if not password:
        return 0, "Empty"

    score = 0
    if len(password) >= 6:
        score += 1
    if len(password) >= 10:
        score += 1
    if re.search(r"[A-Za-z]", password) and re.search(r"\d", password):
        score += 1
    if re.search(r"[^A-Za-z0-9]", password):
        score += 1

    labels = {0: "Very weak", 1: "Weak", 2: "Fair", 3: "Strong", 4: "Very strong"}
    return score, labels[score]


# ---------------------------------------------------------------------
# Login / session management
# ---------------------------------------------------------------------
def login_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user against the ``users`` table.

    Returns
    -------
    dict | None
        On success, a dictionary with ``user_id``, ``username`` and
        ``role`` (never the password hash).  Returns ``None`` when the
        credentials are invalid or the account does not exist.
    """
    if not username or not password:
        return None

    username = str(username).strip()

    try:
        record = db.fetch_one(
            """
            SELECT user_id, username, password_hash, role, created_at
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username,),
        )
    except db.DatabaseError:
        return None

    if not record:
        return None

    if not check_password(password, record.get("password_hash", "")):
        return None

    return {
        "user_id": record["user_id"],
        "username": record["username"],
        "role": record["role"],
        "created_at": record.get("created_at"),
    }


def authenticate(username: str, password: str) -> tuple[bool, str, Optional[dict]]:
    """
    Wrapper around :func:`login_user` that also returns a message.

    Returns ``(success, message, user_dict)`` - convenient for showing an
    error inside a Streamlit form.
    """
    if not username or not password:
        return False, "Please enter both username and password.", None

    try:
        exists = db.fetch_one(
            "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE",
            (str(username).strip(),),
        )
    except db.DatabaseError as exc:
        return False, f"Database unavailable: {exc}", None

    if not exists:
        return False, "Invalid username or password.", None

    user = login_user(username, password)
    if user is None:
        return False, "Invalid username or password.", None

    return True, f"Welcome, {user['username']}.", user


# ---------------------------------------------------------------------
# Streamlit session helpers
# ---------------------------------------------------------------------
def set_current_user(user: Optional[dict]) -> None:
    """Store the authenticated user in the Streamlit session."""
    try:
        import streamlit as st

        st.session_state["user"] = user
        st.session_state.setdefault("login_time", None)
    except Exception:  # pragma: no cover - outside Streamlit
        pass


def get_current_user() -> Optional[dict]:
    """
    Return the currently logged-in user from ``st.session_state``.

    Returns ``None`` when nobody is logged in, so every page can use it
    as a guard:

    >>> user = get_current_user()
    >>> if user is None:
    ...     show_login_page()
    """
    try:
        import streamlit as st

        user = st.session_state.get("user")
        if isinstance(user, dict) and user.get("username"):
            return user
        return None
    except Exception:  # pragma: no cover - outside Streamlit
        return None


def current_user_id() -> Optional[int]:
    """Convenience accessor for the logged-in user's primary key."""
    user = get_current_user()
    return user.get("user_id") if user else None


def current_username() -> str:
    """Convenience accessor for the logged-in username."""
    user = get_current_user()
    return user.get("username", "system") if user else "system"


def is_authenticated() -> bool:
    """True when a user session is active."""
    return get_current_user() is not None


def is_admin() -> bool:
    """
    True when the logged-in user has the Admin/Commander role.

    This is the single gate that hides/disables every create, update and
    delete control in the application.
    """
    user = get_current_user()
    return bool(user and user.get("role") == "Admin")


def is_viewer() -> bool:
    """True when the logged-in user is a read-only Viewer/Dispatcher."""
    user = get_current_user()
    return bool(user and user.get("role") == "Viewer")


def logout_user() -> None:
    """Clear the authentication state (called by the Logout button)."""
    try:
        import streamlit as st

        st.session_state["user"] = None
        st.session_state.pop("login_time", None)
    except Exception:  # pragma: no cover - outside Streamlit
        pass


# ---------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------
def create_user(username: str, password: str, role: str = "Viewer") -> tuple[bool, str]:
    """
    Register a new user account.

    Returns ``(success, message)``.
    """
    username = (username or "").strip()

    if not USERNAME_PATTERN.match(username):
        return (
            False,
            "Username must be 3-32 characters and may contain only letters, "
            "numbers, dots, underscores and hyphens.",
        )
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if role not in VALID_ROLES:
        return False, f"Invalid role. Allowed roles are {', '.join(VALID_ROLES)}."

    try:
        existing = db.fetch_one(
            "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE", (username,)
        )
        if existing:
            return False, "That username is already taken."

        user_id = db.execute_query(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, hash_password(password), role),
        )
        db.log_activity(
            "USER_CREATED",
            f"New {role} account '{username}' created (user_id={user_id})",
            actor=current_username(),
        )
        return True, f"User '{username}' created successfully as {role}."
    except db.DatabaseError as exc:
        return False, str(exc)
    except ValueError as exc:
        return False, str(exc)


def change_password(user_id: int, new_password: str) -> tuple[bool, str]:
    """Reset the password of an existing account."""
    if not new_password or len(new_password) < 6:
        return False, "Password must be at least 6 characters long."
    try:
        affected = db.execute_query(
            "UPDATE users SET password_hash = ? WHERE user_id = ?",
            (hash_password(new_password), int(user_id)),
        )
        if affected == 0:
            return False, "User not found."
        db.log_activity(
            "PASSWORD_CHANGED",
            f"Password changed for user_id={user_id}",
            actor=current_username(),
        )
        return True, "Password updated successfully."
    except db.DatabaseError as exc:
        return False, str(exc)


def list_users() -> list[dict]:
    """Return all accounts (without password hashes) for the admin page."""
    try:
        return db.fetch_all(
            """
            SELECT user_id, username, role, created_at
            FROM users
            ORDER BY role, username
            """
        )
    except db.DatabaseError:
        return []


def delete_user(user_id: int) -> tuple[bool, str]:
    """Delete an account, protecting the last remaining Admin."""
    try:
        target = db.fetch_one("SELECT username, role FROM users WHERE user_id = ?", (int(user_id),))
        if not target:
            return False, "User not found."

        if target["role"] == "Admin":
            admins = db.fetch_scalar(
                "SELECT COUNT(*) FROM users WHERE role = 'Admin'", default=0
            )
            if int(admins) <= 1:
                return False, "Cannot delete the only remaining Admin account."

        current = get_current_user()
        if current and int(current.get("user_id", -1)) == int(user_id):
            return False, "You cannot delete the account you are currently signed in with."

        db.execute_query("DELETE FROM users WHERE user_id = ?", (int(user_id),))
        db.log_activity(
            "USER_DELETED",
            f"Account '{target['username']}' deleted",
            actor=current_username(),
        )
        return True, f"User '{target['username']}' deleted."
    except db.DatabaseError as exc:
        return False, str(exc)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = hash_password("npf123")
    print("Hash      :", sample[:48], "...")
    print("Verify ok :", check_password("npf123", sample))
    print("Verify bad:", check_password("wrong", sample))
    print("Strength  :", password_strength("npf123"))
