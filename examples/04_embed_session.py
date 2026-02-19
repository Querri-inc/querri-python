"""Embed sessions — create, refresh, list, and revoke.

Demonstrates:
- The low-level embed session API (create_session, refresh, list, revoke)
- The session token lifecycle for iframe embedding

For the high-level get_session() method, see 05_get_session.py.

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

    ext_id = f"embed_example_{uuid.uuid4().hex[:8]}"
    user_id = None

    try:
        # Create a user for the session
        user = client.users.create(
            email=f"{ext_id}@example.com",
            external_id=ext_id,
        )
        user_id = user.id
        print(f"Created user: {user_id}")

        # Create an embed session
        print("\nCreating embed session...")
        session = client.embed.create_session(
            user_id=user_id,
            origin="https://app.customer.com",
            ttl=900,  # 15 minutes (min: 900, max: 86400)
        )
        print(f"  Token: {session.session_token}")
        print(f"  Expires in: {session.expires_in}s")

        # Refresh the session (extends lifetime, old token is revoked)
        print("\nRefreshing session...")
        refreshed = client.embed.refresh_session(
            session_token=session.session_token,
        )
        print(f"  New token: {refreshed.session_token}")

        # List active sessions
        print("\nListing sessions...")
        session_list = client.embed.list_sessions(limit=10)
        print(f"  Active sessions: {len(session_list.data)}")
        for s in session_list.data:
            print(f"    {s.session_token[:20]}... (user: {s.user_id})")

        # Revoke the session
        print("\nRevoking session...")
        revoke_resp = client.embed.revoke_session(refreshed.session_token)
        print(f"  Revoked: {revoke_resp.revoked}")

    finally:
        if user_id:
            client.users.delete(user_id)
            print(f"\nDeleted user {user_id}")
        client.close()


if __name__ == "__main__":
    main()
