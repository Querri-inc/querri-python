"""Quick start — initialize the client and list projects.

Demonstrates:
- Creating a Querri client from environment variables
- Listing projects with auto-pagination
- Accessing Pydantic model attributes

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os

from querri import Querri

def main():
    # Option 1: Explicit credentials
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
        # host="http://localhost",  # uncomment for local development
    )

    # Option 2: Let the SDK read from environment variables
    # client = Querri()

    print("Projects:")
    for project in client.projects.list():
        print(f"  - {project.name} ({project.id})")

    client.close()


if __name__ == "__main__":
    main()
