"""Unit tests for the user management module."""

import importlib
import pytest
import main as m


def _reset():
    """Reset module state between tests."""
    m.users.clear()
    m._next_id = 1


# ---------------------------------------------------------------------------
# add_user
# ---------------------------------------------------------------------------

def test_add_user_returns_user():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    assert u["name"] == "Alice"
    assert u["email"] == "alice@example.com"
    assert isinstance(u["id"], int)


def test_add_user_increments_id():
    _reset()
    u1 = m.add_user("Alice", "alice@example.com")
    u2 = m.add_user("Bob", "bob@example.com")
    assert u2["id"] == u1["id"] + 1


def test_add_user_empty_name_raises():
    _reset()
    with pytest.raises(ValueError):
        m.add_user("", "a@b.com")


def test_add_user_invalid_email_raises():
    _reset()
    with pytest.raises(ValueError):
        m.add_user("Alice", "not-an-email")


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------

def test_get_user_existing():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    assert m.get_user(u["id"]) == u


def test_get_user_missing_returns_none():
    _reset()
    assert m.get_user(999) is None


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------

def test_list_users_empty():
    _reset()
    assert m.list_users() == []


def test_list_users_returns_all():
    _reset()
    m.add_user("Alice", "alice@example.com")
    m.add_user("Bob", "bob@example.com")
    assert len(m.list_users()) == 2


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------

def test_update_user_name():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    updated = m.update_user(u["id"], name="Alicia")
    assert updated["name"] == "Alicia"


def test_update_user_email():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    updated = m.update_user(u["id"], email="new@example.com")
    assert updated["email"] == "new@example.com"


def test_update_user_missing_returns_none():
    _reset()
    assert m.update_user(999, name="Ghost") is None


def test_update_user_invalid_email_raises():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    with pytest.raises(ValueError):
        m.update_user(u["id"], email="bad-email")


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------

def test_delete_user_existing():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    assert m.delete_user(u["id"]) is True
    assert m.get_user(u["id"]) is None


def test_delete_user_missing_returns_false():
    _reset()
    assert m.delete_user(999) is False


def test_delete_user_already_deleted():
    _reset()
    u = m.add_user("Alice", "alice@example.com")
    m.delete_user(u["id"])
    assert m.delete_user(u["id"]) is False
