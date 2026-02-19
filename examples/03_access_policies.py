"""Access policies — create, assign users, and the setup() convenience.

Demonstrates:
- Creating policies with row filters and source scoping
- Assigning and removing users from policies
- The setup() convenience method (create + assign in one call)
- Listing and deleting policies

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

    policy_id = None
    setup_policy_id = None
    user_id = None
    ext_id = f"policy_example_{uuid.uuid4().hex[:8]}"

    try:
        # Create a test user first
        user = client.users.create(
            email=f"{ext_id}@example.com",
            external_id=ext_id,
        )
        user_id = user.id
        print(f"Created test user: {user_id}")

        # --- Method 1: Manual create + assign ---

        print("\n--- Manual policy creation ---")
        policy = client.policies.create(
            name=f"Example Policy {ext_id}",
            description="Row-level security for APAC region",
            source_ids=["src_abc"],  # replace with real source IDs
            row_filters=[
                {"column": "region", "values": ["APAC"]},
                {"column": "department", "values": ["Sales", "Marketing"]},
            ],
        )
        policy_id = policy.id
        print(f"Created policy: {policy.id} ({policy.name})")

        # Assign user to the policy (idempotent)
        assign_resp = client.policies.assign_users(
            policy.id,
            user_ids=[user_id],
        )
        print(f"Assigned users: {assign_resp.assigned_user_ids}")

        # Get policy details
        details = client.policies.get(policy.id)
        print(f"Policy details: {details.name}, user_ids={details.user_ids}")

        # List policies (filter by name)
        policies = client.policies.list(name=policy.name)
        print(f"Found {len(policies)} policy matching name filter")

        # Remove user from policy
        remove_resp = client.policies.remove_user(policy.id, user_id)
        print(f"Removed user: {remove_resp.removed}")

        # --- Method 2: setup() convenience ---

        print("\n--- setup() convenience method ---")
        setup_policy = client.policies.setup(
            name=f"Setup Example {ext_id}",
            sources=["src_abc"],  # replace with real source IDs
            row_filters={"region": ["APAC"], "department": "Sales"},
            users=[user_id],
        )
        setup_policy_id = setup_policy.id
        print(f"Created + assigned in one call: {setup_policy.id}")

    finally:
        # Cleanup
        if policy_id:
            client.policies.delete(policy_id)
            print(f"\nDeleted policy {policy_id}")
        if setup_policy_id:
            client.policies.delete(setup_policy_id)
            print(f"Deleted policy {setup_policy_id}")
        if user_id:
            client.users.delete(user_id)
            print(f"Deleted user {user_id}")
        client.close()


if __name__ == "__main__":
    main()
