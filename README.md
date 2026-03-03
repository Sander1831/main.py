# main.py

A simple Python user management module providing basic CRUD operations.

## Usage

```python
from main import add_user, get_user, list_users, update_user, delete_user

# Add users
alice = add_user("Alice", "alice@example.com")
bob   = add_user("Bob",   "bob@example.com")

# List all users
print(list_users())

# Get a single user
print(get_user(alice["id"]))

# Update a user
update_user(alice["id"], email="alice@newdomain.com")

# Delete a user
delete_user(bob["id"])
```

Run the built-in demo:

```bash
python main.py
```