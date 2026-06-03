"""
Workflow store with optional JSON-file persistence so backend restarts
don't lose state. Each entry is written to `audits/state/<workflow_id>.json`
after every mutation (best-effort, non-fatal on write failure).

On startup, `WorkflowStore.load_from_disk()` reads all JSONs back into memory.
Pydantic agent results are stored as plain dicts after a round-trip; existing
consumers (deploy endpoint, /full) already handle both shapes.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "audits" / "state"


def new_workflow_id() -> str:
    return f"wf-{uuid.uuid4().hex[:12]}"


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert datetimes, Pydantic models, and sets to JSON-safe types."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, set):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    # Pydantic v2 model
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:
            return str(obj)
    # Dataclass or arbitrary - fall back to repr
    return str(obj)


def _restore_datetimes(entry: dict[str, Any]) -> dict[str, Any]:
    """Walk a loaded entry and turn known datetime ISO strings back into datetime objects."""
    for key in ("started_at", "finished_at"):
        v = entry.get(key)
        if isinstance(v, str):
            try:
                entry[key] = datetime.fromisoformat(v)
            except ValueError:
                pass
    return entry


class WorkflowStore:
    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._persist_dir: Optional[Path] = persist_dir or _STATE_DIR
        if self._persist_dir is not None:
            try:
                self._persist_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                self._persist_dir = None

    # ----- persistence helpers -----
    def _save_entry_sync(self, entry: dict[str, Any]) -> None:
        if self._persist_dir is None:
            return
        wf_id = entry.get("workflow_id")
        if not wf_id:
            return
        path = self._persist_dir / f"{wf_id}.json"
        try:
            payload = _to_jsonable(entry)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            # Best-effort - never let persistence break the API flow
            pass

    def _persist(self, workflow_id: str) -> None:
        """Synchronous fire-and-forget save (called while holding the lock)."""
        entry = self._data.get(workflow_id)
        if entry is not None:
            self._save_entry_sync(entry)

    def load_from_disk(self) -> int:
        """Synchronously load all state files into memory. Returns count loaded."""
        if self._persist_dir is None or not self._persist_dir.exists():
            return 0
        loaded = 0
        for f in sorted(self._persist_dir.glob("wf-*.json")):
            try:
                entry = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(entry, dict) or "workflow_id" not in entry:
                    continue
                entry = _restore_datetimes(entry)
                # Default any missing fields the in-memory format expects
                entry.setdefault("trace", [])
                entry.setdefault("started_ts", time.time())
                self._data[entry["workflow_id"]] = entry
                loaded += 1
            except Exception:
                continue
        return loaded

    # ----- API used by main.py -----
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
            self._persist(workflow_id)

    async def append_trace(self, workflow_id: str, line: str) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is not None:
                entry["trace"].append(line)
                # Don't persist on every trace line - too noisy. Phase changes
                # and completions trigger their own saves.

    async def complete(self, workflow_id: str, state: dict[str, Any]) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is None:
                return
            finished_at = datetime.now(timezone.utc)

            requested_mode = state.get("deployment_mode")
            iac = state.get("iac")
            iac_ok = iac is not None and getattr(iac, "workflow_dir", "") != ""

            if state.get("error"):
                entry["status"] = "errored"
            elif requested_mode == "plan_only" and iac_ok:
                entry["status"] = "awaiting_approval"
            else:
                entry["status"] = "completed"

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
            self._persist(workflow_id)

    async def set_phase(self, workflow_id: str, phase: str) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is not None:
                entry["status"] = phase
                self._persist(workflow_id)

    async def patch_state_field(
        self, workflow_id: str, key: str, value: Any
    ) -> None:
        async with self._lock:
            entry = self._data.get(workflow_id)
            if entry is None:
                return
            if entry.get("state") is None:
                entry["state"] = {}
            entry["state"][key] = value
            self._persist(workflow_id)

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
        # One-shot load on first access so a fresh uvicorn process picks up
        # workflows from previous runs automatically.
        try:
            loaded = _store_singleton.load_from_disk()
            if loaded:
                print(f"[store] Loaded {loaded} workflows from disk")
        except Exception as e:
            print(f"[store] load_from_disk failed: {e}")
    return _store_singleton
