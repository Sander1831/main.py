"""Simple user management module."""

import re
import threading

_lock = threading.Lock()
users = {}
_next_id = 1

_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


def _validate(name: str, email: str) -> None:
    """Raise ValueError if name or email is invalid."""
    if not name or not name.strip():
        raise ValueError("name must not be empty")
    if not _EMAIL_RE.match(email):
        raise ValueError(f"invalid email address: {email!r}")


def add_user(name: str, email: str) -> dict:
    """Add a new user and return the created user."""
    global _next_id
    _validate(name, email)
    with _lock:
        user = {"id": _next_id, "name": name, "email": email}
        users[_next_id] = user
        _next_id += 1
    return user


def get_user(user_id: int) -> dict | None:
    """Return a user by ID, or None if not found."""
    with _lock:
        return users.get(user_id)


def list_users() -> list:
    """Return a list of all users."""
    with _lock:
        return list(users.values())


def update_user(user_id: int, name: str = None, email: str = None) -> dict | None:
    """Update a user's name and/or email. Returns updated user or None if not found."""
    if name is not None and not name.strip():
        raise ValueError("name must not be empty")
    if email is not None and not _EMAIL_RE.match(email):
        raise ValueError(f"invalid email address: {email!r}")
    with _lock:
        user = users.get(user_id)
        if user is None:
            return None
        if name is not None:
            user["name"] = name
        if email is not None:
            user["email"] = email
    return user


def delete_user(user_id: int) -> bool:
    """Delete a user by ID. Returns True if deleted, False if not found."""
    with _lock:
        if user_id in users:
            del users[user_id]
            return True
    return False


if __name__ == "__main__":
    print("=== User Management Demo ===")

    u1 = add_user("Alice", "alice@example.com")
    u2 = add_user("Bob", "bob@example.com")
    print("Added users:", list_users())

    update_user(u1["id"], email="alice@newdomain.com")
    print("After update:", get_user(u1["id"]))

    delete_user(u2["id"])
    print("After delete:", list_users())
