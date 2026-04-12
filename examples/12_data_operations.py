"""Data operations — create sources, append rows, replace data.

Demonstrates:
- Creating a data source with initial rows
- Appending rows to an existing source
- Replacing all data in a source
- Querying a source with SQL
- Fetching paginated source data
- Source sharing (share_source, org_share_source)

Prerequisites:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
"""

import os

from querri import Querri

def main():
    client = Querri(
        api_key=os.environ["QUERRI_API_KEY"],
        org_id=os.environ["QUERRI_ORG_ID"],
    )

    source_id = None

    try:
        # ---------------------------------------------------------------
        # 1. Create a data source with initial rows
        # ---------------------------------------------------------------
        print("Creating data source with initial rows...")
        source = client.sources.create_data_source(
            name="SDK Example - Sales",
            rows=[
                {"region": "APAC", "product": "Widget A", "revenue": 1200},
                {"region": "EMEA", "product": "Widget B", "revenue": 800},
                {"region": "APAC", "product": "Widget C", "revenue": 1500},
            ],
        )
        source_id = source.id
        print(f"  Created source: {source.id} ({source.name})")
        print(f"  Columns: {source.columns}")
        print(f"  Row count: {source.row_count}")

        # ---------------------------------------------------------------
        # 2. Append rows to the source
        # ---------------------------------------------------------------
        print("\nAppending rows...")
        append_result = client.sources.append_rows(
            source_id,
            rows=[
                {"region": "AMER", "product": "Widget D", "revenue": 2000},
                {"region": "AMER", "product": "Widget E", "revenue": 950},
            ],
        )
        print(f"  Appended {append_result.rows_affected} rows")

        # ---------------------------------------------------------------
        # 3. Query the source with SQL
        # ---------------------------------------------------------------
        print("\nQuerying source...")
        result = client.sources.query(
            sql=f"SELECT region, SUM(revenue) as total FROM src WHERE 1=1 GROUP BY region",
            source_id=source_id,
        )
        print(f"  Total rows: {result.total_rows}")
        for row in result.data:
            print(f"    {row}")

        # ---------------------------------------------------------------
        # 4. Fetch paginated source data
        # ---------------------------------------------------------------
        print("\nFetching source data (page 1)...")
        page = client.sources.source_data(source_id, page=1, page_size=3)
        print(f"  Page rows: {len(page.data)}")
        print(f"  Total rows: {page.total_rows}")

        # ---------------------------------------------------------------
        # 5. Replace all data
        # ---------------------------------------------------------------
        print("\nReplacing all data...")
        replace_result = client.sources.replace_data(
            source_id,
            rows=[
                {"region": "APAC", "product": "New Widget", "revenue": 5000},
            ],
        )
        print(f"  Replaced with {replace_result.rows_affected} rows")

        # Verify replacement
        updated = client.sources.get(source_id)
        print(f"  New row count: {updated.get('row_count')}")

        # ---------------------------------------------------------------
        # 6. Source sharing (optional — requires another user)
        # ---------------------------------------------------------------
        # Share a data source with a specific user:
        #   client.sharing.share_source(source_id, user_id="usr_...", permission="view")
        #
        # Or enable org-wide access:
        #   client.sharing.org_share_source(source_id, enabled=True, permission="view")

    finally:
        if source_id:
            client.sources.delete(source_id)
            print(f"\nDeleted source {source_id}")
        client.close()


if __name__ == "__main__":
    main()
