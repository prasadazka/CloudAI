"""
In-memory workflow store. Async-safe.
Swap for Redis/Supabase in production by implementing the same interface.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def new_workflow_id() -> str:
    return f"wf-{uuid.uuid4().hex[:12]}"


class WorkflowStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(
        self, workflow_id: str, customer_name: str, user_request: str
    ) -> None:
        async with self._lock:
            self._data[workflow_id] = {
                "workflow_id": workflow_id,
                "customer_name": customer_name,
                "user_request": user_request,
                "status": "running",
                "trace": [],
                "started_at": datetime.now(timezone.utc),
                "started_ts": time.time(),
                "finished_at": None,
                "duration_sec": None,
                "final_decision": None,
                "audit_pdf_path": None,
                "site_count": 0,
                "estimated_cost_inr_monthly": None,
                "error": None,
                "state": None,
            }

    async def append_trace(self, workflow_id: str, line: str) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is not None:
                entry["trace"].append(line)

    async def complete(self, workflow_id: str, state: dict[str, Any]) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is None:
                return
            finished_at = datetime.now(timezone.utc)
            entry["status"] = "completed" if not state.get("error") else "errored"
            entry["finished_at"] = finished_at
            entry["duration_sec"] = round(time.time() - entry["started_ts"], 2)
            entry["final_decision"] = state.get("final_decision")
            entry["audit_pdf_path"] = state.get("audit_pdf_path")
            entry["error"] = state.get("error")
            entry["state"] = state
            intake = state.get("intake")
            if intake is not None:
                entry["site_count"] = getattr(intake, "site_count", 0) or 0
            policy = state.get("policy")
            if policy is not None:
                entry["estimated_cost_inr_monthly"] = getattr(
                    policy, "estimated_cost_inr_monthly", None
                )

    async def get(self, workflow_id: str) -> Optional[dict[str, Any]]:
        async with self._lock:
            return self._data.get(workflow_id)

    async def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self._lock:
            ordered = sorted(
                self._data.values(),
                key=lambda x: x["started_ts"],
                reverse=True,
            )
            return ordered[:limit]


_store_singleton: Optional[WorkflowStore] = None


def get_store() -> WorkflowStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = WorkflowStore()
    return _store_singleton
