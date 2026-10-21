"""get_session() deep dive — the flagship SDK method.

This is the single most important method in the SDK. It combines:
1. User resolution (get-or-create by external_id)
2. Access policy application (inline spec or policy_ids reference)
3. Embed session creation

All in one call — the complete white-label embedding workflow.

Demonstrates:
- String shorthand (existing user)
- Dict form (auto-create user)
- Inline access spec (sources + filters)
- policy_ids reference
- Origin locking
- Running the session as a Custom Role (role=...)

Tip: For data source sharing without inline access specs, see also
client.sharing.share_source() and client.sharing.org_share_source()
in example 12_data_operations.py.

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os
import uuid

from querri import APIError, Querri

def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    ext_id = f"gs_example_{uuid.uuid4().hex[:8]}"
    email = f"{ext_id}@example.com"
    policy_id = None

    try:
        # ---------------------------------------------------------------
        # 1. Dict form — auto-creates the user if they don't exist
        # ---------------------------------------------------------------
        print("=== Dict form (auto-create user) ===")
        session = client.embed.get_session(
            user={
                "external_id": ext_id,
                "email": email,
                "first_name": "Alice",
                "last_name": "Smith",
                "role": "member",
            },
            ttl=3600,
        )
        print(f"  session_token: {session['session_token']}")
        print(f"  user_id:       {session['user_id']}")
        print(f"  external_id:   {session['external_id']}")
        print(f"  expires_in:    {session['expires_in']}s")

        # Revoke the session so we can create fresh ones below
        client.embed.revoke_session(session["session_token"])

        # ---------------------------------------------------------------
        # 2. String shorthand — user must already exist
        # ---------------------------------------------------------------
        print("\n=== String shorthand (existing user) ===")
        session = client.embed.get_session(
            user=ext_id,  # just the external_id string
            ttl=7200,
        )
        print(f"  session_token: {session['session_token']}")
        client.embed.revoke_session(session["session_token"])

        # ---------------------------------------------------------------
        # 3. Inline access spec — auto-managed policy
        # ---------------------------------------------------------------
        print("\n=== Inline access spec ===")
        session = client.embed.get_session(
            user=ext_id,
            access={
                "sources": ["src_sales", "src_marketing"],
                "filters": {
                    "region": ["APAC", "EMEA"],
                    "department": "Sales",
                },
            },
            origin="https://app.customer.com",
            ttl=3600,
        )
        print(f"  session_token: {session['session_token']}")
        print("  (SDK auto-created a policy named sdk_auto_<hash>)")
        client.embed.revoke_session(session["session_token"])

        # ---------------------------------------------------------------
        # 4. Reference existing policies by ID
        # ---------------------------------------------------------------
        print("\n=== Reference existing policies ===")
        # First, create a policy to reference
        policy = client.policies.create(name=f"ref_policy_{ext_id}")
        policy_id = policy.id

        session = client.embed.get_session(
            user=ext_id,
            access={"policy_ids": [policy_id]},
        )
        print(f"  session_token: {session['session_token']}")
        client.embed.revoke_session(session["session_token"])

        # ---------------------------------------------------------------
        # 5. No access param — user keeps existing policies
        # ---------------------------------------------------------------
        print("\n=== No access (preserve existing) ===")
        session = client.embed.get_session(user=ext_id)
        print(f"  session_token: {session['session_token']}")
        client.embed.revoke_session(session["session_token"])

        # ---------------------------------------------------------------
        # 6. Custom Role — run the session as one of the org's roles
        # ---------------------------------------------------------------
        # role is a role id or key from Settings → Roles. It is NOT the
        # user dict's "role" (the org role, admin/member). Decide it on the
        # server from your own auth — never take it from the browser.
        # Set QUERRI_EXAMPLE_ROLE to try it (e.g. "analyst").
        role = os.environ.get("QUERRI_EXAMPLE_ROLE")
        if role:
            print("\n=== Custom Role ===")
            try:
                session = client.embed.get_session(user=ext_id, role=role)
                print(f"  role_id:       {session.get('role_id')}")
                client.embed.revoke_session(session["session_token"])
            except APIError as e:
                # role_not_found (404), role_not_allowed, role_disabled,
                # insufficient_scope (granting a role the user does not hold
                # needs embed:role:assign) or seat_change_required (403).
                print(f"  {type(e).__name__} {e.code}: {e.message}")

    finally:
        # Cleanup
        if policy_id:
            client.policies.delete(policy_id)
        # Delete the auto-created user
        page = client.users.list(external_id=ext_id)
        for u in page.data:
            client.users.delete(u.id)
            print(f"\nDeleted user {u.id}")
        client.close()


if __name__ == "__main__":
    main()
