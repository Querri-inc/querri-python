"""User management — full CRUD lifecycle.

Demonstrates:
- create, get, list, update, delete
- get_or_create idempotency by external_id
- Filtering users by external_id

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os
import uuid

from querri import Querri

def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    ext_id = f"example_{uuid.uuid4().hex[:8]}"
    email = f"{ext_id}@example.com"
    user_id = None

    try:
        # Create a user
        print("Creating user...")
        user = client.users.create(
            email=email,
            external_id=ext_id,
            first_name="Alice",
            last_name="Smith",
            role="member",
        )
        user_id = user.id
        print(f"  Created: {user.id} ({user.email})")

        # Get by ID
        print("\nFetching user by ID...")
        fetched = client.users.get(user_id)
        print(f"  Got: {fetched.id} ({fetched.email})")

        # List with external_id filter
        print("\nListing users with external_id filter...")
        page = client.users.list(external_id=ext_id)
        for u in page.data:
            print(f"  Found: {u.id} ({u.email})")

        # Update
        print("\nUpdating user...")
        updated = client.users.update(user_id, first_name="Alicia")
        print(f"  Updated: {updated.id}")

        # get_or_create — idempotent
        print("\nTesting get_or_create idempotency...")
        user_a = client.users.get_or_create(
            external_id=ext_id,
            email=email,
            first_name="Alice",
        )
        user_b = client.users.get_or_create(
            external_id=ext_id,
            email=email,
        )
        assert user_a.id == user_b.id, "get_or_create should return the same user"
        print(f"  Same user returned both times: {user_a.id}")

    finally:
        # Cleanup
        if user_id:
            print(f"\nDeleting user {user_id}...")
            client.users.delete(user_id)
            print("  Deleted.")
        client.close()


if __name__ == "__main__":
    main()
