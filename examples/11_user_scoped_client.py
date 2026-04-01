"""User-scoped client — as_user() for FGA-filtered operations.

Demonstrates:
- Creating a session with get_session()
- Creating a user-scoped client with as_user()
- Listing projects/dashboards filtered by user access policies
- Context manager usage for cleanup

The user-scoped client calls the internal API (/api) with an embed
session token. Resources are automatically filtered by the user's
assigned access policies — only data they're allowed to see is returned.

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

    ext_id = f"scoped_example_{uuid.uuid4().hex[:8]}"
    session = None

    try:
        # ---------------------------------------------------------------
        # 1. Create a session for the user
        # ---------------------------------------------------------------
        print("Creating session with inline access rules...")
        session = client.embed.get_session(
            user={
                "external_id": ext_id,
                "email": f"{ext_id}@example.com",
                "first_name": "Scoped",
                "last_name": "User",
            },
            access={
                "sources": ["src_sales"],
                "filters": {"region": ["APAC"]},
            },
            ttl=900,
        )
        print(f"  session_token: {session['session_token'][:20]}...")
        print(f"  user_id: {session['user_id']}")

        # ---------------------------------------------------------------
        # 2. Create a user-scoped client
        # ---------------------------------------------------------------
        print("\nCreating user-scoped client...")
        with client.as_user(session) as user_client:
            # ---------------------------------------------------------------
            # 3. List projects — automatically FGA-filtered
            # ---------------------------------------------------------------
            print("\n=== Projects (FGA-filtered) ===")
            for project in user_client.projects.list(limit=10):
                print(f"  {project.name} ({project.id})")

            # ---------------------------------------------------------------
            # 4. List dashboards — also FGA-filtered
            # ---------------------------------------------------------------
            print("\n=== Dashboards (FGA-filtered) ===")
            for dashboard in user_client.dashboards.list(limit=10):
                print(f"  {dashboard.name} ({dashboard.id})")

            # ---------------------------------------------------------------
            # 5. Data access is also filtered by row-level policies
            # ---------------------------------------------------------------
            print("\n=== Data sources (FGA-filtered) ===")
            for source in user_client.data.sources(limit=10):
                print(f"  {source.name} ({source.id})")

        print("\nUser-scoped client closed (via context manager).")

    finally:
        # Cleanup: revoke session and delete test user
        if session:
            client.embed.revoke_session(session["session_token"])
            print(f"\nRevoked session")
            # Clean up the auto-created user
            users = client.users.list(external_id=ext_id)
            for u in users:
                client.users.delete(u.id)
                print(f"Deleted user {u.id}")
        client.close()


if __name__ == "__main__":
    main()
