from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker, Session
from tool_governance.core.models import Base, ToolRegistry, ToolStatus
from tool_governance.core.scanner import _TOOL_METADATA
from tool_governance.core.approval import ApprovalClient
from tool_governance.core.metrics import (
    TOOL_REGISTERED,
    TOOL_ACTIVATED,
    TOOL_REJECTED,
    TOOL_APPROVALS,
    TOOL_ACTIVE_COUNT,
    TOOL_STATUS_COUNT,
    APPROVAL_PENDING_DURATION,
    CACHE_HITS,
    CACHE_MISSES,
    CACHE_INVALIDATIONS,
    REGISTRY_OPERATION_DURATION,
)


class ToolRegistryService:
    def __init__(self, db_url: str = "sqlite:///./tools.db", cache_ttl: int = 60):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_expiry = {}

    def scan_and_register(self) -> str:
        new_count = 0
        updated_count = 0
        auto_activated_count = 0
        pending_count = 0

        with self.SessionLocal() as session:
            with session.begin():
                for tool_name, metadata in _TOOL_METADATA.items():
                    existing = session.execute(
                        select(ToolRegistry).where(ToolRegistry.name == tool_name)
                    ).scalar_one_or_none()

                    permission_level = metadata["permission_level"]

                    if existing:
                        existing.description = metadata["description"]
                        existing.permission_level = permission_level
                        existing.schema_json = metadata["schema_json"]
                        updated_count += 1
                    else:
                        initial_status, approval_required, quiet_period_until = self._determine_initial_status(permission_level)

                        new_tool = ToolRegistry(
                            name=tool_name,
                            description=metadata["description"],
                            schema_json=metadata["schema_json"],
                            permission_level=permission_level,
                            status=initial_status,
                            created_by=metadata["creator"],
                            approval_required=approval_required,
                            quiet_period_until=quiet_period_until,
                        )
                        session.add(new_tool)
                        new_count += 1

                        TOOL_REGISTERED.labels(permission_level=permission_level).inc()

                        if initial_status == ToolStatus.ACTIVE:
                            auto_activated_count += 1
                            TOOL_ACTIVATED.labels(permission_level=permission_level).inc()
                        else:
                            pending_count += 1

        self._update_status_metrics()
        return f"Registered {new_count} new tools ({auto_activated_count} auto-activated, {pending_count} pending approval), updated {updated_count} existing tools"

    def _determine_initial_status(self, permission_level: str) -> tuple:
        if permission_level == "public":
            return ToolStatus.ACTIVE, 0, None
        elif permission_level == "internal":
            return ToolStatus.PENDING, 1, None
        elif permission_level == "default":
            return ToolStatus.PENDING, 1, None
        elif permission_level in ("confidential", "restricted"):
            quiet_until = datetime.now() + timedelta(hours=24)
            return ToolStatus.PENDING, 2, quiet_until
        else:
            return ToolStatus.PENDING, 1, None

    def get_active_tools(self) -> List[Dict[str, Any]]:
        cache_key = "active_tools"
        now = datetime.now()

        if cache_key in self._cache and now < self._cache_expiry[cache_key]:
            CACHE_HITS.inc()
            return self._cache[cache_key]

        CACHE_MISSES.inc()

        with self.SessionLocal() as session:
            tools = session.execute(
                select(ToolRegistry).where(ToolRegistry.status == ToolStatus.ACTIVE)
            ).scalars().all()
            result = [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "schema_json": t.schema_json,
                    "permission_level": t.permission_level,
                    "status": t.status,
                    "created_by": t.created_by,
                    "created_at": t.created_at,
                    "approved_at": t.approved_at,
                    "call_count": t.call_count,
                    "last_called_at": t.last_called_at,
                    "approval_count": t.approval_count,
                    "approval_required": t.approval_required,
                    "quiet_period_until": t.quiet_period_until,
                }
                for t in tools
            ]

        self._cache[cache_key] = result
        self._cache_expiry[cache_key] = now + timedelta(seconds=self.cache_ttl)
        return result

    def invalidate_cache(self) -> None:
        CACHE_INVALIDATIONS.inc()
        self._cache.clear()
        self._cache_expiry.clear()

    def approve_tool(self, tool_name: str, approver: str) -> Dict[str, Any]:
        with self.SessionLocal() as session:
            with session.begin():
                tool = session.execute(
                    select(ToolRegistry).where(ToolRegistry.name == tool_name)
                ).scalar_one_or_none()

                if not tool:
                    return {"success": False, "message": "Tool not found"}

                if tool.status == ToolStatus.ACTIVE:
                    return {"success": False, "message": "Tool is already active"}

                if tool.status == ToolStatus.REJECTED:
                    return {"success": False, "message": "Tool has been rejected"}

                if approver in (tool.approvers or []):
                    return {"success": False, "message": f"User '{approver}' has already approved this tool"}

                tool.approval_count += 1
                tool.approvers = tool.approvers or []
                tool.approvers.append(approver)
                TOOL_APPROVALS.labels(tool_name=tool_name).inc()

                if tool.approval_count >= tool.approval_required:
                    if tool.quiet_period_until and datetime.now() < tool.quiet_period_until:
                        remaining_hours = (tool.quiet_period_until - datetime.now()).total_seconds() / 3600
                        return {
                            "success": True,
                            "message": f"Approval threshold reached ({tool.approval_count}/{tool.approval_required}), waiting for quiet period ({remaining_hours:.1f} hours remaining)",
                            "approval_count": tool.approval_count,
                            "approval_required": tool.approval_required,
                            "quiet_period_until": tool.quiet_period_until,
                        }
                    else:
                        tool.status = ToolStatus.ACTIVE
                        tool.approved_at = datetime.now()

                        if tool.created_at:
                            pending_duration = (datetime.now() - tool.created_at).total_seconds()
                            APPROVAL_PENDING_DURATION.labels(permission_level=tool.permission_level).observe(pending_duration)

                        TOOL_ACTIVATED.labels(permission_level=tool.permission_level).inc()
                        self.invalidate_cache()
                        self._update_status_metrics()
                        return {
                            "success": True,
                            "message": f"Tool '{tool_name}' approved by '{approver}'",
                            "approval_count": tool.approval_count,
                            "approval_required": tool.approval_required,
                        }
                else:
                    return {
                        "success": True,
                        "message": f"Approval progress: {tool.approval_count}/{tool.approval_required}, still need {tool.approval_required - tool.approval_count} more approvals",
                        "approval_count": tool.approval_count,
                        "approval_required": tool.approval_required,
                    }

    def reject_tool(self, tool_name: str) -> bool:
        with self.SessionLocal() as session:
            with session.begin():
                tool = session.execute(
                    select(ToolRegistry).where(ToolRegistry.name == tool_name)
                ).scalar_one_or_none()
                if tool:
                    tool.status = ToolStatus.REJECTED
                    TOOL_REJECTED.labels(permission_level=tool.permission_level).inc()
                    self.invalidate_cache()
                    self._update_status_metrics()
                    return True
                return False

    def _update_status_metrics(self) -> None:
        with self.SessionLocal() as session:
            status_counts = {}
            level_counts = {}
            all_tools = session.execute(select(ToolRegistry)).scalars().all()
            for tool in all_tools:
                status_counts[tool.status] = status_counts.get(tool.status, 0) + 1
                if tool.status == ToolStatus.ACTIVE:
                    level_counts[tool.permission_level] = level_counts.get(tool.permission_level, 0) + 1

            for status in [ToolStatus.ACTIVE, ToolStatus.PENDING, ToolStatus.REJECTED, ToolStatus.DEPRECATED]:
                TOOL_STATUS_COUNT.labels(status=status).set(status_counts.get(status, 0))

            for level in ["public", "internal", "confidential", "restricted", "default"]:
                TOOL_ACTIVE_COUNT.labels(permission_level=level).set(level_counts.get(level, 0))

    def get_tools_by_status(self, status: str = "all") -> List[Dict[str, Any]]:
        with self.SessionLocal() as session:
            query = select(ToolRegistry)
            if status != "all":
                query = query.where(ToolRegistry.status == status)
            tools = session.execute(query).scalars().all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "permission_level": t.permission_level,
                    "status": t.status,
                    "created_by": t.created_by,
                    "created_at": t.created_at,
                    "approved_at": t.approved_at,
                    "call_count": t.call_count,
                    "last_called_at": t.last_called_at,
                    "approval_count": t.approval_count,
                    "approval_required": t.approval_required,
                    "quiet_period_until": t.quiet_period_until,
                }
                for t in tools
            ]

    def submit_approval(self, tool_name: str, client: ApprovalClient) -> Dict[str, Any]:
        with self.SessionLocal() as session:
            with session.begin():
                tool = session.execute(
                    select(ToolRegistry).where(ToolRegistry.name == tool_name)
                ).scalar_one_or_none()

                if not tool:
                    return {"success": False, "message": "Tool not found"}

                if tool.status != ToolStatus.PENDING:
                    return {"success": False, "message": f"Tool status is {tool.status}, only pending tools can submit approval"}

                result = client.submit_approval(
                    tool_name=tool.name,
                    tool_description=tool.description,
                    creator=tool.created_by,
                    permission_level=tool.permission_level,
                )

                tool.approval_id = result["approval_id"]
                tool.approval_platform = type(client).__name__.replace("ApprovalClient", "").lower()

                return {"success": True, "approval_id": result["approval_id"], "message": result["message"]}

    def sync_approval_status(self, client: ApprovalClient, tool_name: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []

        with self.SessionLocal() as session:
            with session.begin():
                query = select(ToolRegistry).where(
                    ToolRegistry.status == ToolStatus.PENDING,
                    ToolRegistry.approval_id.isnot(None)
                )
                if tool_name:
                    query = query.where(ToolRegistry.name == tool_name)

                tools = session.execute(query).scalars().all()

                for tool in tools:
                    try:
                        status_info = client.get_approval_status(tool.approval_id)
                        remote_status = status_info.get("status", "unknown")
                        approver = status_info.get("approver", "external")

                        if remote_status == "approved":
                            if approver not in (tool.approvers or []):
                                tool.approval_count += 1
                                tool.approvers = tool.approvers or []
                                tool.approvers.append(approver)

                            if tool.approval_count >= tool.approval_required:
                                if tool.quiet_period_until and datetime.now() < tool.quiet_period_until:
                                    remaining_hours = (tool.quiet_period_until - datetime.now()).total_seconds() / 3600
                                    results.append({
                                        "tool_name": tool.name,
                                        "status": "waiting_quiet_period",
                                        "message": f"Approval threshold reached ({tool.approval_count}/{tool.approval_required}), waiting for quiet period ({remaining_hours:.1f} hours remaining)"
                                    })
                                else:
                                    tool.status = ToolStatus.ACTIVE
                                    tool.approved_at = datetime.now()
                                    self.invalidate_cache()
                                    results.append({"tool_name": tool.name, "status": "approved"})
                            else:
                                results.append({
                                    "tool_name": tool.name,
                                    "status": "partial_approval",
                                    "message": f"Approval progress: {tool.approval_count}/{tool.approval_required}"
                                })
                        elif remote_status == "rejected":
                            tool.status = ToolStatus.REJECTED
                            self.invalidate_cache()
                            results.append({"tool_name": tool.name, "status": "rejected"})
                        else:
                            results.append({"tool_name": tool.name, "status": "still_pending"})
                    except Exception as e:
                        results.append({"tool_name": tool.name, "status": "error", "error": str(e)})

        return results