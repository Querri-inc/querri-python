"""Projects — list, get, create, run, check status, steps, and data.

Demonstrates:
- Listing projects with auto-pagination
- Creating and deleting projects
- Submitting a project for execution
- Checking run status
- Listing steps and fetching step data

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os
import time
import uuid

from querri import Querri, NotFoundError

def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    ext_id = f"proj_example_{uuid.uuid4().hex[:8]}"
    user_id = None
    project_id = None

    try:
        # Create a user to own the project
        user = client.users.create(
            email=f"{ext_id}@example.com",
            external_id=ext_id,
        )
        user_id = user.id

        # List existing projects
        print("=== Listing projects ===")
        for project in client.projects.list(limit=5):
            print(f"  {project.name} ({project.id})")

        # Create a project
        print("\n=== Creating project ===")
        project = client.projects.create(
            name=f"SDK Example {ext_id}",
            user_id=user_id,
            description="Created by querri-python SDK example",
        )
        project_id = project.id
        print(f"  Created: {project.id} ({project.name})")

        # Get project details
        print("\n=== Getting project details ===")
        details = client.projects.get(project_id)
        print(f"  Name: {details.name}")
        print(f"  ID:   {details.id}")

        # Update project
        print("\n=== Updating project ===")
        updated = client.projects.update(project_id, name=f"Updated {ext_id}")
        print(f"  New name: {updated.name}")

        # Submit for execution
        print("\n=== Submitting for execution ===")
        run = client.projects.run(project_id, user_id=user_id)
        print(f"  Status: {run.status}")

        # Poll for completion
        print("\n=== Checking run status ===")
        for _ in range(5):
            status = client.projects.run_status(project_id)
            print(f"  is_running: {status.is_running}, status: {status.status}")
            if not status.is_running:
                break
            time.sleep(2)

        # List steps
        print("\n=== Listing steps ===")
        steps = client.projects.list_steps(project_id)
        print(f"  Found {len(steps)} steps")
        for step in steps:
            print(f"    {step.id}: {step.name}")

            # Get step data (if available)
            try:
                data = client.projects.get_step_data(
                    project_id, step.id,
                    page=1, page_size=5,
                )
                print(f"      Columns: {data.columns}")
                print(f"      Rows: {len(data.rows)}")
            except NotFoundError:
                print("      (no data)")

    finally:
        # Cleanup
        if project_id:
            client.projects.delete(project_id)
            print(f"\nDeleted project {project_id}")
        if user_id:
            client.users.delete(user_id)
            print(f"Deleted user {user_id}")
        client.close()


if __name__ == "__main__":
    main()
