#!/usr/bin/env python3
"""Flask server for Querri embed + SDK explorer.

Python equivalent of the PHP react-embed example (querri-session.php + sdk.php).

Usage:
    export QUERRI_API_KEY="qk_..."
    export QUERRI_ORG_ID="org_..."
    export QUERRI_HOST="https://your-org.querri.com"
    python examples/web-embed/server.py

Then open http://localhost:5050 in your browser.
"""

import os
import sys

from flask import Flask, jsonify, request, send_from_directory
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from querri import Querri
from querri._exceptions import APIError, QuerriError
from querri._pagination import SyncCursorPage

app = Flask(__name__)

# -- Configuration ----------------------------------------------------------
# All values come from environment variables — no hardcoded credentials.

QUERRI_HOST = os.environ.get("QUERRI_HOST", "https://app.querri.com")

client = Querri(
    api_key=os.environ.get("QUERRI_API_KEY", ""),
    org_id=os.environ.get("QUERRI_ORG_ID", ""),
    host=QUERRI_HOST,
)

# -- Demo user for the embed session endpoint -------------------------------
# Customize these for your environment, or override via request body.

DEMO_USER = {
    "external_id": "demo-user",
    "email": "demo@example.com",
    "first_name": "Demo",
    "last_name": "User",
}

# Optional: restrict what the demo user can see via row-level filters.
# Set to None to skip access filtering, or provide inline access spec:
#   DEMO_ACCESS = {
#       "sources": ["your_source_name"],
#       "filters": {"column_name": ["value1", "value2"]},
#   }
DEMO_ACCESS = None


# -- Helpers ----------------------------------------------------------------

def serialize(obj):
    """Convert SDK response objects to JSON-serializable dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, SyncCursorPage):
        page = obj._ensure_first_page()
        return {
            "data": [item.model_dump() for item in page.data],
            "has_more": page.has_more,
            "next_cursor": page.next_cursor,
            "total": page.total,
        }
    if isinstance(obj, list):
        return [serialize(item) for item in obj]
    if isinstance(obj, dict):
        return obj
    return obj


# -- Routes -----------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(os.path.dirname(__file__), "index.html")


@app.route("/api/config")
def config():
    """Return server config for the frontend."""
    return jsonify({"serverUrl": QUERRI_HOST})


@app.route("/api/querri-session", methods=["POST"])
def querri_session():
    """Create embed session — mirrors PHP querri-session.php."""
    try:
        kwargs = dict(user=DEMO_USER, origin=request.headers.get("Origin"), ttl=3600)
        if DEMO_ACCESS:
            kwargs["access"] = DEMO_ACCESS
        session = client.embed.get_session(**kwargs)
        return jsonify(session)
    except APIError as e:
        return jsonify({"error": e.message, "code": e.code}), e.status
    except QuerriError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/user-projects", methods=["POST"])
def user_projects():
    """List FGA-filtered projects — mirrors PHP user-projects.php."""
    try:
        session = client.embed.get_session(user=DEMO_USER, ttl=900)
        with client.as_user(session) as uc:
            projects = [{"id": p.id, "name": p.name, "status": p.status}
                        for p in uc.projects.list(limit=50)]
        return jsonify({
            "user_external_id": DEMO_USER["external_id"],
            "session_token": session["session_token"],
            "projects": projects,
        })
    except APIError as e:
        return jsonify({"error": e.message, "code": e.code}), e.status
    except QuerriError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sdk", methods=["POST"])
def sdk_explorer():
    """SDK action router — mirrors PHP sdk.php.

    POST {"action": "users.list", "params": {...}}
    """
    body = request.get_json(force=True)
    action = body.get("action", "")
    p = body.get("params", {})

    try:
        result = _dispatch(action, p)
        return jsonify(serialize(result))

    except APIError as e:
        return jsonify({
            "error": e.message, "code": e.code,
            "type": e.type, "status": e.status,
        }), e.status
    except QuerriError as e:
        return jsonify({"error": str(e)}), 500
    except (KeyError, TypeError) as e:
        return jsonify({"error": f"Missing parameter: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500


def _dispatch(action: str, p: dict):
    """Dispatch an action string to the appropriate SDK method."""

    # ─── Users ─────────────────────────────────────────────
    if action == "users.list":
        return client.users.list(
            limit=p.get("limit", 50),
            external_id=p.get("external_id"),
        )
    if action == "users.create":
        return client.users.create(
            email=p["email"],
            external_id=p.get("external_id"),
            first_name=p.get("first_name"),
            last_name=p.get("last_name"),
            role=p.get("role", "member"),
        )
    if action == "users.get":
        return client.users.get(p["user_id"])
    if action == "users.update":
        return client.users.update(
            p["user_id"],
            role=p.get("role"),
            first_name=p.get("first_name"),
            last_name=p.get("last_name"),
        )
    if action == "users.delete":
        return client.users.delete(p["user_id"])
    if action == "users.getOrCreate":
        return client.users.get_or_create(
            p["external_id"],
            email=p.get("email"),
            first_name=p.get("first_name"),
            last_name=p.get("last_name"),
            role=p.get("role", "member"),
        )
    if action == "users.removeExternalId":
        return client.users.remove_external_id(p["external_id"])

    # ─── Embed ─────────────────────────────────────────────
    if action == "embed.createSession":
        return client.embed.create_session(
            user_id=p["user_id"],
            origin=p.get("origin"),
            ttl=p.get("ttl", 3600),
        )
    if action == "embed.refreshSession":
        return client.embed.refresh_session(p["session_token"])
    if action == "embed.listSessions":
        return client.embed.list_sessions(limit=p.get("limit", 100))
    if action == "embed.revokeSession":
        return client.embed.revoke_session(p.get("session_id"), session_token=p.get("session_token"))
    if action == "embed.revokeUserSessions":
        return {"revoked": client.embed.revoke_user_sessions(p["user_id"])}
    if action == "embed.getSession":
        return client.embed.get_session(
            user=p.get("user", p.get("external_id", "")),
            access=p.get("access"),
            origin=p.get("origin"),
            ttl=p.get("ttl", 3600),
        )

    # ─── Policies ──────────────────────────────────────────
    if action == "policies.list":
        return client.policies.list(
            name=p.get("name"),
            limit=p.get("limit", 50),
        )
    if action == "policies.create":
        return client.policies.create(
            name=p["name"],
            description=p.get("description"),
            source_ids=p.get("source_ids"),
            row_filters=p.get("row_filters"),
        )
    if action == "policies.get":
        return client.policies.get(p["policy_id"])
    if action == "policies.update":
        return client.policies.update(
            p["policy_id"],
            name=p.get("name"),
            description=p.get("description"),
            source_ids=p.get("source_ids"),
            row_filters=p.get("row_filters"),
        )
    if action == "policies.delete":
        return client.policies.delete(p["policy_id"])
    if action == "policies.assignUsers":
        return client.policies.assign_users(p["policy_id"], user_ids=p["user_ids"])
    if action == "policies.removeUser":
        return client.policies.remove_user(p["policy_id"], p["user_id"])
    if action == "policies.replaceUserPolicies":
        return client.policies.replace_user_policies(p["user_id"], policy_ids=p["policy_ids"])
    if action == "policies.resolve":
        return client.policies.resolve(p["user_id"], p["source_id"])
    if action == "policies.columns":
        return client.policies.columns(source_id=p.get("source_id"))
    if action == "policies.setup":
        return client.policies.setup(
            name=p["name"],
            sources=p.get("sources"),
            row_filters=p.get("row_filters"),
            users=p.get("users"),
            description=p.get("description"),
        )

    # ─── Dashboards ────────────────────────────────────────
    if action == "dashboards.list":
        return client.dashboards.list(
            limit=p.get("limit", 25),
            user_id=p.get("user_id"),
        )
    if action == "dashboards.create":
        return client.dashboards.create(name=p["name"], description=p.get("description"))
    if action == "dashboards.get":
        return client.dashboards.get(p["dashboard_id"])
    if action == "dashboards.update":
        return client.dashboards.update(
            p["dashboard_id"],
            name=p.get("name"),
            description=p.get("description"),
        )
    if action == "dashboards.delete":
        return client.dashboards.delete(p["dashboard_id"])
    if action == "dashboards.refresh":
        return client.dashboards.refresh(p["dashboard_id"])
    if action == "dashboards.refreshStatus":
        return client.dashboards.refresh_status(p["dashboard_id"])

    # ─── Projects ──────────────────────────────────────────
    if action == "projects.list":
        return client.projects.list(
            limit=p.get("limit", 25),
            user_id=p.get("user_id"),
        )
    if action == "projects.create":
        return client.projects.create(
            name=p["name"], user_id=p["user_id"],
            description=p.get("description"),
        )
    if action == "projects.get":
        return client.projects.get(p["project_id"])
    if action == "projects.update":
        return client.projects.update(
            p["project_id"],
            name=p.get("name"),
            description=p.get("description"),
        )
    if action == "projects.delete":
        return client.projects.delete(p["project_id"])
    if action == "projects.run":
        return client.projects.run(p["project_id"], user_id=p["user_id"])
    if action == "projects.runStatus":
        return client.projects.run_status(p["project_id"])
    if action == "projects.runCancel":
        return client.projects.run_cancel(p["project_id"])
    if action == "projects.listSteps":
        return client.projects.list_steps(p["project_id"])
    if action == "projects.getStepData":
        return client.projects.get_step_data(
            p["project_id"], p["step_id"],
            page=p.get("page", 1),
            page_size=p.get("page_size", 100),
        )

    # ─── Chats ─────────────────────────────────────────────
    if action == "chats.create":
        return client.projects.chats.create(p["project_id"], name=p.get("name"))
    if action == "chats.list":
        return client.projects.chats.list(p["project_id"], limit=p.get("limit", 25))
    if action == "chats.get":
        return client.projects.chats.get(p["project_id"], p["chat_id"])
    if action == "chats.delete":
        return client.projects.chats.delete(p["project_id"], p["chat_id"])
    if action == "chats.cancel":
        return client.projects.chats.cancel(p["project_id"], p["chat_id"])

    # ─── Data ──────────────────────────────────────────────
    if action == "data.sources":
        return client.data.sources(limit=p.get("limit", 50))
    if action == "data.source":
        return client.data.source(p["source_id"])
    if action == "data.createSource":
        return client.data.create_source(name=p["name"], rows=p["rows"])
    if action == "data.appendRows":
        return client.data.append_rows(p["source_id"], rows=p["rows"])
    if action == "data.replaceData":
        return client.data.replace_data(p["source_id"], rows=p["rows"])
    if action == "data.deleteSource":
        return client.data.delete_source(p["source_id"])
    if action == "data.query":
        return client.data.query(
            sql=p["sql"], source_id=p["source_id"],
            page=p.get("page", 1),
            page_size=p.get("page_size", 100),
        )
    if action == "data.sourceData":
        return client.data.source_data(
            p["source_id"],
            page=p.get("page", 1),
            page_size=p.get("page_size", 100),
        )

    # ─── Sources & Connectors ──────────────────────────────
    if action == "sources.listConnectors":
        return client.sources.list_connectors()
    if action == "sources.list":
        return client.sources.list()
    if action == "sources.create":
        return client.sources.create(
            name=p["name"], connector_id=p["connector_id"],
            config=p.get("config"),
        )
    if action == "sources.update":
        return client.sources.update(
            p["source_id"],
            name=p.get("name"),
            config=p.get("config"),
        )
    if action == "sources.delete":
        return client.sources.delete(p["source_id"])
    if action == "sources.sync":
        return client.sources.sync(p["source_id"])

    # ─── Files ─────────────────────────────────────────────
    if action == "files.list":
        return client.files.list()
    if action == "files.get":
        return client.files.get(p["file_id"])
    if action == "files.delete":
        return client.files.delete(p["file_id"])

    # ─── API Keys ──────────────────────────────────────────
    if action == "keys.create":
        return client.keys.create(
            name=p["name"], scopes=p["scopes"],
            expires_in_days=p.get("expires_in_days"),
            rate_limit_per_minute=p.get("rate_limit_per_minute"),
            ip_allowlist=p.get("ip_allowlist"),
        )
    if action == "keys.list":
        return client.keys.list()
    if action == "keys.get":
        return client.keys.get(p["key_id"])
    if action == "keys.delete":
        return client.keys.delete(p["key_id"])

    # ─── Audit ─────────────────────────────────────────────
    if action == "audit.list":
        return client.audit.list(
            actor_id=p.get("actor_id"),
            target_id=p.get("target_id"),
            action=p.get("action_filter"),
            start_date=p.get("start_date"),
            end_date=p.get("end_date"),
        )

    # ─── Usage ─────────────────────────────────────────────
    if action == "usage.org":
        return client.usage.org_usage(period=p.get("period", "current_month"))
    if action == "usage.user":
        return client.usage.user_usage(p["user_id"], period=p.get("period", "current_month"))

    # ─── Sharing ───────────────────────────────────────────
    if action == "sharing.shareProject":
        return client.sharing.share_project(
            p["project_id"], user_id=p["user_id"],
            permission=p.get("permission", "view"),
        )
    if action == "sharing.revokeProjectShare":
        return client.sharing.revoke_project_share(p["project_id"], p["user_id"])
    if action == "sharing.listProjectShares":
        return client.sharing.list_project_shares(p["project_id"])
    if action == "sharing.shareDashboard":
        return client.sharing.share_dashboard(
            p["dashboard_id"], user_id=p["user_id"],
            permission=p.get("permission", "view"),
        )
    if action == "sharing.revokeDashboardShare":
        return client.sharing.revoke_dashboard_share(p["dashboard_id"], p["user_id"])
    if action == "sharing.listDashboardShares":
        return client.sharing.list_dashboard_shares(p["dashboard_id"])
    if action == "sharing.shareSource":
        return client.sharing.share_source(
            p["source_id"], user_id=p["user_id"],
            permission=p.get("permission", "view"),
        )
    if action == "sharing.orgShareSource":
        return client.sharing.org_share_source(
            p["source_id"],
            enabled=bool(p.get("enabled", False)),
            permission=p.get("permission", "view"),
        )

    raise ValueError(f"Unknown action: {action}")


if __name__ == "__main__":
    print(f"\n  Querri Python SDK — Embed + Explorer")
    print(f"  Server:  {QUERRI_HOST}")
    print(f"  Open:    http://localhost:5050\n")
    app.run(host="0.0.0.0", port=5050, debug=True)
