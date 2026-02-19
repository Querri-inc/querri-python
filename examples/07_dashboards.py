"""Dashboards — list, get, create, refresh, and delete.

Demonstrates:
- Listing dashboards
- Getting dashboard details
- Creating and deleting dashboards
- Triggering a refresh and checking status

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os
import uuid

from querri import Querri, NotFoundError

def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    dashboard_id = None

    try:
        # List dashboards
        print("=== Listing dashboards ===")
        dashboards = client.dashboards.list(limit=10)
        for d in dashboards:
            print(f"  {d.name} ({d.id})")
        if not dashboards:
            print("  (none)")

        # Create a dashboard
        print("\n=== Creating dashboard ===")
        ext_id = uuid.uuid4().hex[:8]
        dashboard = client.dashboards.create(
            name=f"SDK Example Dashboard {ext_id}",
            description="Created by querri-python SDK example",
        )
        dashboard_id = dashboard.id
        print(f"  Created: {dashboard.id} ({dashboard.name})")

        # Get dashboard details
        print("\n=== Getting dashboard details ===")
        details = client.dashboards.get(dashboard_id)
        print(f"  Name: {details.name}")
        print(f"  ID:   {details.id}")

        # Update
        print("\n=== Updating dashboard ===")
        client.dashboards.update(dashboard_id, name=f"Updated Dashboard {ext_id}")
        print("  Updated name")

        # Trigger refresh
        print("\n=== Triggering refresh ===")
        refresh = client.dashboards.refresh(dashboard_id)
        print(f"  Status: {refresh.status}")

        # Check refresh status
        status = client.dashboards.refresh_status(dashboard_id)
        print(f"  Refresh status: {status.status}")

    finally:
        # Cleanup
        if dashboard_id:
            client.dashboards.delete(dashboard_id)
            print(f"\nDeleted dashboard {dashboard_id}")
        client.close()


if __name__ == "__main__":
    main()
