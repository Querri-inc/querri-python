"""Usage metrics resource."""

from __future__ import annotations

from .._base_client import AsyncHTTPClient, SyncHTTPClient
from ..types.usage import OrgUsageReport, UserUsageReport


class Usage:
    """Synchronous usage metrics resource.

    Usage::

        org = client.usage.org_usage()
        user = client.usage.user_usage("user_id")
    """

    def __init__(self, http: SyncHTTPClient) -> None:
        self._http = http

    def org_usage(
        self,
        *,
        period: str = "current_month",
    ) -> OrgUsageReport:
        """Get organization-level usage summary.

        Args:
            period: One of "current_month", "last_month", "last_30_days".

        Returns:
            OrgUsageReport with period, totals, and counts.
        """
        resp = self._http.get("/usage", params={"period": period})
        return OrgUsageReport.model_validate(resp.json())

    def user_usage(
        self,
        user_id: str,
        *,
        period: str = "current_month",
    ) -> UserUsageReport:
        """Get per-user usage breakdown.

        Args:
            user_id: The user ID.
            period: One of "current_month", "last_month", "last_30_days".

        Returns:
            UserUsageReport with period, ai_messages, and daily_breakdown.
        """
        resp = self._http.get(
            f"/usage/users/{user_id}",
            params={"period": period},
        )
        return UserUsageReport.model_validate(resp.json())


class AsyncUsage:
    """Asynchronous usage metrics resource.

    Usage::

        org = await client.usage.org_usage()
        user = await client.usage.user_usage("user_id")
    """

    def __init__(self, http: AsyncHTTPClient) -> None:
        self._http = http

    async def org_usage(
        self,
        *,
        period: str = "current_month",
    ) -> OrgUsageReport:
        """Get organization-level usage summary.

        Args:
            period: One of "current_month", "last_month", "last_30_days".

        Returns:
            UsageReport with period, totals, and details.
        """
        resp = await self._http.get("/usage", params={"period": period})
        return OrgUsageReport.model_validate(resp.json())

    async def user_usage(
        self,
        user_id: str,
        *,
        period: str = "current_month",
    ) -> UserUsageReport:
        """Get per-user usage breakdown.

        Args:
            user_id: The user ID.
            period: One of "current_month", "last_month", "last_30_days".

        Returns:
            UserUsageReport with period, ai_messages, and daily_breakdown.
        """
        resp = await self._http.get(
            f"/usage/users/{user_id}",
            params={"period": period},
        )
        return UserUsageReport.model_validate(resp.json())
