"""Error handling — catching specific exceptions and retry patterns.

Demonstrates:
- The exception hierarchy
- Catching specific error types
- Accessing error attributes (status, type, code, message, request_id)
- Retry pattern for rate limits
- ConfigError for missing credentials

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os
import time

from querri import (
    Querri,
    APIError,
    AuthenticationError,
    ConfigError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ServerError,
)


def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    # ----------------------------------------------------------
    # 1. NotFoundError (404)
    # ----------------------------------------------------------
    print("=== NotFoundError ===")
    try:
        client.projects.get("00000000-0000-0000-0000-000000000000")
    except NotFoundError as e:
        print(f"  Caught NotFoundError:")
        print(f"    status:     {e.status}")
        print(f"    message:    {e.message}")
        print(f"    type:       {e.type}")
        print(f"    code:       {e.code}")
        print(f"    request_id: {e.request_id}")

    # ----------------------------------------------------------
    # 2. Catching multiple error types
    # ----------------------------------------------------------
    print("\n=== Multiple error types ===")
    try:
        client.users.get("nonexistent_user_id")
    except NotFoundError:
        print("  User not found (404)")
    except AuthenticationError:
        print("  Bad API key (401)")
    except ValidationError as e:
        print(f"  Bad request (400): {e.message}")
    except ServerError as e:
        print(f"  Server error ({e.status}): {e.message}")
    except APIError as e:
        # Catch-all for any API error
        print(f"  API error ({e.status}): {e.message}")

    # ----------------------------------------------------------
    # 3. Retry pattern for rate limits
    # ----------------------------------------------------------
    print("\n=== Rate limit retry pattern ===")

    def get_project_with_retry(project_id: str, max_retries: int = 3):
        """Example retry pattern for rate-limited requests."""
        for attempt in range(max_retries):
            try:
                return client.projects.get(project_id)
            except RateLimitError as e:
                wait = e.retry_after or (2 ** attempt)
                print(f"  Rate limited, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            except NotFoundError:
                raise  # Don't retry 404s
        raise RuntimeError("Max retries exceeded")

    try:
        get_project_with_retry("00000000-0000-0000-0000-000000000000")
    except NotFoundError:
        print("  (Got expected 404 — retry logic works correctly)")

    # ----------------------------------------------------------
    # 4. ConfigError — missing credentials
    # ----------------------------------------------------------
    print("\n=== ConfigError ===")
    try:
        bad_client = Querri(api_key=None, org_id=None)
    except ConfigError as e:
        print(f"  Caught ConfigError: {e.message}")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
