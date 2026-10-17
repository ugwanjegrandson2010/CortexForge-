"""Account and email integration for CortexForge.

Implements account-based authentication on top of the existing learner_id
system, with email verification, password reset, and SMTP email sending.

Security constraints inherited from security.py:
  * All passwords hashed with PBKDF2 (stdlib only, no external deps).
  * All tokens generated with secrets, compared with constant_time_compare.
  * All emails sanitised before sending.
  * Rate limiting on all auth endpoints.
  * No credentials in logs.

Database schema additions:
    account       email, password_hash, created_at, verified
    account_link  maps account_id -> learner_id
    verify_token  time-limited tokens for email verification
    reset_token   time-limited tokens for password reset
    auth_session  session tokens with expiry
    rate_limit    sliding-window rate limit tracker
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import smtplib
import ssl
import threading
import time
from dataclasses import dataclass, field, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any

from .security import (SecurityError, constant_time_compare, load_json_only,
                       safe_join, sanitise_text, secure_token)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    account_id    TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    created_at    REAL NOT NULL,
    verified      INTEGER NOT NULL DEFAULT 0,
    last_login    REAL
);

CREATE TABLE IF NOT EXISTS account_link (
    account_id   TEXT NOT NULL,
    learner_id   TEXT NOT NULL,
    created_at   REAL NOT NULL,
    PRIMARY KEY (account_id, learner_id),
    FOREIGN KEY (account_id) REFERENCES account(account_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS verify_token (
    token_id    TEXT PRIMARY KEY,
    account_id  TEXT NOT NULL,
    email       TEXT NOT NULL,
    purpose     TEXT NOT NULL,  -- 'verify' | 'reset'
    expires_at  REAL NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verify_account ON verify_token(account_id);

CREATE TABLE IF NOT EXISTS auth_session (
    session_id  TEXT PRIMARY KEY,
    account_id  TEXT NOT NULL,
    learner_id  TEXT NOT NULL,
    token_hash  TEXT NOT NULL,
    expires_at  REAL NOT NULL,
    created_at  REAL NOT NULL,
    last_used   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_account ON auth_session(account_id);

CREATE TABLE IF NOT EXISTS rate_limit (
    key         TEXT PRIMARY KEY,
    window_start REAL NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0
);
"""

# Token lifetimes
VERIFY_TOKEN_TTL = 3600 * 24    # 24 hours
RESET_TOKEN_TTL = 3600 * 2      # 2 hours
SESSION_TTL = 3600 * 24 * 7    # 7 days

# PBKDF2 iterations (OWASP 2023 recommendation: 600k for SHA-256)
PBKDF2_ITERATIONS = 600_000

# Rate limit windows
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10     # attempts per window

# Email validation regex (simplified RFC 5322)
EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2, stdlib only)
# ---------------------------------------------------------------------------

def _pbkdf2_hash(password: str, salt: bytes | None = None) -> str:
    """Hash password with PBKDF2-HMAC-SHA256. Returns 'salt:hash' hex."""
    if salt is None:
        salt = secure_token(16).encode()
    dk = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored 'salt:hash'."""
    try:
        salt_hex, _ = stored.split(':', 1)
        salt = bytes.fromhex(salt_hex)
        expected = _pbkdf2_hash(password, salt)
        return constant_time_compare(expected, stored)
    except (ValueError, AttributeError):
        return False


def validate_password(password: str) -> str:
    """Validate password strength. Returns error message or empty string."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 256:
        return "Password must be at most 256 characters"
    if not re.search(r'[a-z]', password):
        return "Password must contain a lowercase letter"
    if not re.search(r'[A-Z]', password):
        return "Password must contain an uppercase letter"
    if not re.search(r'\d', password):
        return "Password must contain a digit"
    return ""


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

@dataclass
class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    window: int = RATE_LIMIT_WINDOW
    max_attempts: int = RATE_LIMIT_MAX
    _storage: dict[str, list[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, key: str) -> bool:
        """Return True if the action is allowed, False if rate limited."""
        now = time.time()
        with self._lock:
            timestamps = self._storage.get(key, [])
            # Remove expired entries
            timestamps = [t for t in timestamps if now - t < self.window]
            if len(timestamps) >= self.max_attempts:
                self._storage[key] = timestamps
                return False
            timestamps.append(now)
            self._storage[key] = timestamps
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._storage.pop(key, None)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

@dataclass
class SmtpConfig:
    """SMTP configuration for sending email."""

    host: str = "localhost"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_address: str = ""
    from_name: str = "CortexForge"
    timeout: int = 10

    @classmethod
    def for_gmail(cls, username: str, password: str) -> "SmtpConfig":
        return cls(
            host="smtp.gmail.com",
            port=587,
            username=username,
            password=password,
            use_tls=True,
            from_address=username,
            from_name="CortexForge",
        )

    @classmethod
    def for_outlook(cls, username: str, password: str) -> "SmtpConfig":
        return cls(
            host="smtp-mail.outlook.com",
            port=587,
            username=username,
            password=password,
            use_tls=True,
            from_address=username,
            from_name="CortexForge",
        )

    @classmethod
    def for_yahoo(cls, username: str, password: str) -> "SmtpConfig":
        return cls(
            host="smtp.mail.yahoo.com",
            port=587,
            username=username,
            password=password,
            use_tls=True,
            from_address=username,
            from_name="CortexForge",
        )

    @classmethod
    def from_dict(cls, d: dict) -> "SmtpConfig":
        return cls(
            host=str(d.get("host", "localhost")),
            port=int(d.get("port", 587)),
            username=str(d.get("username", "")),
            password=str(d.get("password", "")),
            use_tls=bool(d.get("use_tls", True)),
            from_address=str(d.get("from_address", "")),
            from_name=str(d.get("from_name", "CortexForge")),
            timeout=int(d.get("timeout", 10)),
        )


def send_email(
    config: SmtpConfig,
    to_address: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> bool:
    """Send an email via SMTP. Returns True on success, False on failure."""
    if not EMAIL_RE.match(to_address):
        raise SecurityError(f"invalid email address: {to_address}")

    subject = sanitise_text(subject, 500)
    body_text = sanitise_text(body_text, 100_000)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config.from_name} <{config.from_address}>"
    msg["To"] = to_address

    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    try:
        if config.use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(config.host, config.port, timeout=config.timeout) as s:
                s.ehlo()
                s.starttls(context=context)
                s.ehlo()
                if config.username and config.password:
                    s.login(config.username, config.password)
                s.sendmail(config.from_address, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(config.host, config.port, timeout=config.timeout) as s:
                if config.username and config.password:
                    s.login(config.username, config.password)
                s.sendmail(config.from_address, [to_address], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError):
        return False


# ---------------------------------------------------------------------------
# Account manager
# ---------------------------------------------------------------------------

class AccountManager:
    """Manages accounts, sessions, and email verification.

    Integrates with the existing Store for persistence. All operations
    are thread-safe through the store's transaction mechanism.
    """

    def __init__(self, store, smtp_config: SmtpConfig | None = None):
        self.store = store
        self.smtp = smtp_config
        self.rate_limiter = RateLimiter()
        self._init_schema()

    def _init_schema(self) -> None:
        """Create account tables if they don't exist."""
        conn = self.store._conn
        conn.executescript(ACCOUNT_SCHEMA)

    # -- account lifecycle -------------------------------------------------

    def create_account(
        self, email: str, password: str, display_name: str = "",
    ) -> dict:
        """Create a new account. Returns account dict with learner_id."""
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            raise SecurityError("invalid email address")

        pw_error = validate_password(password)
        if pw_error:
            raise SecurityError(pw_error)

        display_name = sanitise_text(display_name, 200)

        account_id = "acc-" + secure_token(16)
        password_hash = _pbkdf2_hash(password)
        now = time.time()

        # Check if email already exists
        existing = self.store._one(
            "SELECT account_id FROM account WHERE email = ?", (email,)
        )
        if existing:
            raise SecurityError("email already registered")

        with self.store.transaction():
            self.store._exec(
                "INSERT INTO account(account_id, email, password_hash, "
                "display_name, created_at, verified) VALUES(?,?,?,?,?,?)",
                (account_id, email, password_hash, display_name, now, 0),
            )
            # Create default learner_id from email
            learner_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', email.split('@')[0])
            learner_id = learner_id[:64]
            self.link_learner(account_id, learner_id)
            # Send verification email
            self._send_verification_email(account_id, email)

        return {
            "account_id": account_id,
            "email": email,
            "display_name": display_name,
            "learner_id": learner_id,
            "verified": False,
            "created_at": now,
        }

    def verify_email(self, token: str) -> dict:
        """Verify an email address using a verification token."""
        now = time.time()
        row = self.store._one(
            "SELECT account_id, email, purpose, expires_at, used "
            "FROM verify_token WHERE token_id = ?",
            (token,),
        )
        if not row:
            raise SecurityError("invalid token")
        if row["used"]:
            raise SecurityError("token already used")
        if now > row["expires_at"]:
            raise SecurityError("token expired")
        if row["purpose"] != "verify":
            raise SecurityError("wrong token purpose")

        account_id = row["account_id"]
        with self.store.transaction():
            self.store._exec(
                "UPDATE account SET verified = 1 WHERE account_id = ?",
                (account_id,),
            )
            self.store._exec(
                "UPDATE verify_token SET used = 1 WHERE token_id = ?",
                (token,),
            )

        return {"verified": True, "account_id": account_id}

    def login(self, email: str, password: str) -> dict:
        """Authenticate and create a session."""
        email = email.strip().lower()
        row = self.store._one(
            "SELECT account_id, password_hash, verified FROM account "
            "WHERE email = ?",
            (email,),
        )
        if not row:
            raise SecurityError("invalid credentials")
        if not _verify_password(password, row["password_hash"]):
            raise SecurityError("invalid credentials")

        account_id = row["account_id"]
        now = time.time()

        # Update last login
        self.store._exec(
            "UPDATE account SET last_login = ? WHERE account_id = ?",
            (now, account_id),
        )

        # Get linked learner_id
        link = self.store._one(
            "SELECT learner_id FROM account_link WHERE account_id = ? "
            "LIMIT 1",
            (account_id,),
        )
        if not link:
            # Create a default learner_id
            learner_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', email.split('@')[0])[:64]
            self.link_learner(account_id, learner_id)
        else:
            learner_id = link["learner_id"]

        # Create session
        session_token = secure_token(32)
        session_hash = hashlib.sha256(session_token.encode()).hexdigest()
        session_id = "ses-" + secure_token(16)
        expires_at = now + SESSION_TTL

        self.store._exec(
            "INSERT INTO auth_session(session_id, account_id, learner_id, "
            "token_hash, expires_at, created_at, last_used) "
            "VALUES(?,?,?,?,?,?,?)",
            (session_id, account_id, learner_id, session_hash,
             expires_at, now, now),
        )

        return {
            "session_token": session_token,
            "account_id": account_id,
            "learner_id": learner_id,
            "expires_at": expires_at,
        }

    def logout(self, session_token: str) -> bool:
        """Invalidate a session."""
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        self.store._exec(
            "DELETE FROM auth_session WHERE token_hash = ?", (token_hash,)
        )
        return True

    def validate_session(self, session_token: str) -> dict | None:
        """Validate a session token and return account info."""
        if not session_token:
            return None
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        now = time.time()
        row = self.store._one(
            "SELECT s.account_id, s.learner_id, s.expires_at, "
            "a.email, a.display_name, a.verified "
            "FROM auth_session s "
            "JOIN account a ON s.account_id = a.account_id "
            "WHERE s.token_hash = ?",
            (token_hash,),
        )
        if not row:
            return None
        if now > row["expires_at"]:
            self.store._exec(
                "DELETE FROM auth_session WHERE token_hash = ?", (token_hash,)
            )
            return None
        # Update last_used
        self.store._exec(
            "UPDATE auth_session SET last_used = ? WHERE token_hash = ?",
            (now, token_hash),
        )
        return {
            "account_id": row["account_id"],
            "learner_id": row["learner_id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "verified": bool(row["verified"]),
        }

    def change_password(
        self, account_id: str, old_password: str, new_password: str,
    ) -> bool:
        """Change password after verifying old password."""
        row = self.store._one(
            "SELECT password_hash FROM account WHERE account_id = ?",
            (account_id,),
        )
        if not row:
            raise SecurityError("account not found")
        if not _verify_password(old_password, row["password_hash"]):
            raise SecurityError("invalid password")

        pw_error = validate_password(new_password)
        if pw_error:
            raise SecurityError(pw_error)

        new_hash = _pbkdf2_hash(new_password)
        with self.store.transaction():
            self.store._exec(
                "UPDATE account SET password_hash = ? WHERE account_id = ?",
                (new_hash, account_id),
            )
            # Invalidate all existing sessions
            self.store._exec(
                "DELETE FROM auth_session WHERE account_id = ?", (account_id,)
            )
        return True

    def request_password_reset(self, email: str) -> dict:
        """Send a password reset email. Returns success (always True for security)."""
        email = email.strip().lower()
        row = self.store._one(
            "SELECT account_id FROM account WHERE email = ?", (email,)
        )
        if not row:
            # Don't reveal whether the email exists
            return {"sent": True}

        if not self.smtp:
            return {"sent": False, "reason": "SMTP not configured"}

        account_id = row["account_id"]
        token = secure_token(32)
        token_id = "vrf-" + secure_token(16)
        now = time.time()
        expires_at = now + RESET_TOKEN_TTL

        with self.store.transaction():
            self.store._exec(
                "INSERT INTO verify_token(token_id, account_id, email, "
                "purpose, expires_at, used, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (token_id, account_id, email, "reset", expires_at, 0, now),
            )

        # Send reset email
        reset_url = f"http://localhost:8731/reset?token={token}"
        body = (
            f"You requested a password reset for CortexForge.\n\n"
            f"Click this link to reset your password:\n{reset_url}\n\n"
            f"This link expires in 2 hours.\n"
            f"If you did not request this, you can ignore this email."
        )
        send_email(
            self.smtp, email, "CortexForge Password Reset", body,
        )
        return {"sent": True}

    def reset_password(self, token: str, new_password: str) -> dict:
        """Reset password using a reset token."""
        now = time.time()
        row = self.store._one(
            "SELECT account_id, email, purpose, expires_at, used "
            "FROM verify_token WHERE token_id = ?",
            (token,),
        )
        if not row:
            raise SecurityError("invalid token")
        if row["used"]:
            raise SecurityError("token already used")
        if now > row["expires_at"]:
            raise SecurityError("token expired")
        if row["purpose"] != "reset":
            raise SecurityError("wrong token purpose")

        pw_error = validate_password(new_password)
        if pw_error:
            raise SecurityError(pw_error)

        new_hash = _pbkdf2_hash(new_password)
        with self.store.transaction():
            self.store._exec(
                "UPDATE account SET password_hash = ? WHERE account_id = ?",
                (new_hash, row["account_id"]),
            )
            self.store._exec(
                "UPDATE verify_token SET used = 1 WHERE token_id = ?",
                (token,),
            )
            self.store._exec(
                "DELETE FROM auth_session WHERE account_id = ?",
                (row["account_id"],),
            )
        return {"reset": True}

    # -- learner linking ---------------------------------------------------

    def link_learner(self, account_id: str, learner_id: str) -> None:
        """Link a learner_id to an account."""
        now = time.time()
        self.store._exec(
            "INSERT OR IGNORE INTO account_link(account_id, learner_id, "
            "created_at) VALUES(?,?,?)",
            (account_id, learner_id),
        )

    def get_learners(self, account_id: str) -> list[str]:
        """Get all learner_ids linked to an account."""
        rows = self.store._query(
            "SELECT learner_id FROM account_link WHERE account_id = ? "
            "ORDER BY created_at",
            (account_id,),
        )
        return [r["learner_id"] for r in rows]

    # -- email sending -----------------------------------------------------

    def _send_verification_email(self, account_id: str, email: str) -> bool:
        """Send email verification link."""
        if not self.smtp:
            return False

        token = secure_token(32)
        token_id = "vrf-" + secure_token(16)
        now = time.time()
        expires_at = now + VERIFY_TOKEN_TTL

        with self.store.transaction():
            self.store._exec(
                "INSERT INTO verify_token(token_id, account_id, email, "
                "purpose, expires_at, used, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (token_id, account_id, email, "verify", expires_at, 0, now),
            )

        verify_url = f"http://localhost:8731/verify?token={token}"
        body = (
            f"Welcome to CortexForge!\n\n"
            f"Please verify your email address by clicking this link:\n"
            f"{verify_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"If you did not create this account, you can ignore this email."
        )
        return send_email(
            self.smtp, email, "CortexForge Email Verification", body,
        )

    # -- account management ------------------------------------------------

    def get_account(self, account_id: str) -> dict | None:
        """Get account info by ID."""
        row = self.store._one(
            "SELECT account_id, email, display_name, created_at, verified, "
            "last_login FROM account WHERE account_id = ?",
            (account_id,),
        )
        if not row:
            return None
        return {
            "account_id": row["account_id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "verified": bool(row["verified"]),
            "created_at": row["created_at"],
            "last_login": row["last_login"],
        }

    def update_account(
        self, account_id: str, display_name: str = "", email: str = "",
    ) -> dict:
        """Update account display name and/or email."""
        updates = []
        params = []
        if display_name:
            updates.append("display_name = ?")
            params.append(sanitise_text(display_name, 200))
        if email:
            email = email.strip().lower()
            if not EMAIL_RE.match(email):
                raise SecurityError("invalid email address")
            # Check if email is taken
            existing = self.store._one(
                "SELECT account_id FROM account WHERE email = ? AND "
                "account_id != ?",
                (email, account_id),
            )
            if existing:
                raise SecurityError("email already registered")
            updates.append("email = ?")
            params.append(email)
            # If email changed, mark as unverified
            updates.append("verified = 0")

        if not updates:
            return self.get_account(account_id) or {}

        params.append(account_id)
        set_clause = ", ".join(updates)
        self.store._exec(
            f"UPDATE account SET {set_clause} WHERE account_id = ?", tuple(params)
        )
        return self.get_account(account_id) or {}

    def delete_account(self, account_id: str) -> bool:
        """Delete an account and all associated data."""
        with self.store.transaction():
            self.store._exec(
                "DELETE FROM auth_session WHERE account_id = ?", (account_id,)
            )
            self.store._exec(
                "DELETE FROM verify_token WHERE account_id = ?", (account_id,)
            )
            self.store._exec(
                "DELETE FROM account_link WHERE account_id = ?", (account_id,)
            )
            self.store._exec(
                "DELETE FROM account WHERE account_id = ?", (account_id,)
            )
        return True


__all__ = [
    "AccountManager",
    "SmtpConfig",
    "RateLimiter",
    "send_email",
    "validate_password",
]
