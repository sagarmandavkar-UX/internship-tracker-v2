from __future__ import annotations

import hashlib
import secrets
import sqlite3

from .db import connect, now_iso
from .models import User

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, expected = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def create_user(email: str, password: str, display_name: str) -> tuple[bool, str, int | None]:
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Enter a valid email address.", None
    if len(password) < 10 or password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return False, "Use 10+ characters with uppercase, lowercase, and a number.", None
    created = now_iso()
    try:
        with connect() as conn:
            cur = conn.execute("insert into users(email,password_hash,created_at) values(?,?,?)", (email, hash_password(password), created))
            user_id = int(cur.lastrowid)
            conn.execute(
                "insert into profiles(user_id,display_name,bio,target_role,resume_version,dark_mode,created_at,updated_at) values(?,?,?,?,?,?,?,?)",
                (user_id, display_name.strip() or email.split("@")[0], "", "", "", 0, created, created),
            )
            conn.commit()
        return True, "Account created.", user_id
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists.", None


def authenticate(email: str, password: str) -> User | None:
    with connect() as conn:
        row = conn.execute("select * from users where email=?", (email.strip().lower(),)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return User(row["id"], row["email"], row["created_at"])


def get_user(user_id: int) -> User | None:
    with connect() as conn:
        row = conn.execute("select * from users where id=?", (user_id,)).fetchone()
    return User(row["id"], row["email"], row["created_at"]) if row else None


def get_profile(user_id: int):
    with connect() as conn:
        return conn.execute("select * from profiles where user_id=?", (user_id,)).fetchone()


def update_profile(user_id: int, display_name: str, bio: str, target_role: str, resume_version: str, dark_mode: bool) -> None:
    with connect() as conn:
        conn.execute(
            "update profiles set display_name=?,bio=?,target_role=?,resume_version=?,dark_mode=?,updated_at=? where user_id=?",
            (display_name.strip(), bio.strip(), target_role.strip(), resume_version.strip(), int(dark_mode), now_iso(), user_id),
        )
        conn.commit()
