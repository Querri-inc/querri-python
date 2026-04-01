"""Async client — AsyncQuerri with async/await.

Demonstrates:
- Using AsyncQuerri as a context manager
- Async iteration over paginated results
- Using get_data() instead of .data for async pagination
- Async get_session()

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import asyncio
import os
import uuid

from querri import AsyncQuerri


async def main():
    async with AsyncQuerri() as client:
        # ----------------------------------------------------------
        # List projects (async auto-pagination)
        # ----------------------------------------------------------
        print("=== Projects (async for) ===")
        async for project in client.projects.list(limit=5):
            print(f"  {project.name}")

        # ----------------------------------------------------------
        # Single page with get_data()
        # ----------------------------------------------------------
        print("\n=== Users (single page) ===")
        page = client.users.list(limit=10)
        # NOTE: AsyncCursorPage uses get_data(), not .data
        users = await page.get_data()
        for user in users:
            print(f"  {user.email}")

        # ----------------------------------------------------------
        # User CRUD
        # ----------------------------------------------------------
        ext_id = f"async_example_{uuid.uuid4().hex[:8]}"
        email = f"{ext_id}@example.com"

        print("\n=== Async user create ===")
        user = await client.users.create(
            email=email,
            external_id=ext_id,
            first_name="Async",
            last_name="User",
        )
        print(f"  Created: {user.id}")

        try:
            # ----------------------------------------------------------
            # get_session() works the same way
            # ----------------------------------------------------------
            print("\n=== Async get_session() ===")
            session = await client.embed.get_session(
                user={
                    "external_id": ext_id,
                    "email": email,
                },
                access={"sources": ["src_sales"]},
                ttl=900,
            )
            print(f"  session_token: {session['session_token']}")
            await client.embed.revoke_session(session["session_token"])

            # ----------------------------------------------------------
            # Dashboards (async iteration — no await on .list())
            # ----------------------------------------------------------
            print("\n=== Async dashboards ===")
            async for d in client.dashboards.list(limit=5):
                print(f"  {d.name}")

            # ----------------------------------------------------------
            # Policies (async iteration — no await on .list())
            # ----------------------------------------------------------
            print("\n=== Async policies ===")
            async for p in client.policies.list():
                print(f"  {p.name} ({p.id})")

            # ----------------------------------------------------------
            # Collect all items with to_list()
            # ----------------------------------------------------------
            print("\n=== to_list() convenience ===")
            all_policies = await client.policies.list().to_list()
            print(f"  Total policies: {len(all_policies)}")

        finally:
            await client.users.delete(user.id)
            print(f"\nDeleted user {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
