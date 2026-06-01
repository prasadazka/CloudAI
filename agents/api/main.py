"""
Vi Agentic AI Platform - HTTP API.
Wraps the supervisor in async FastAPI endpoints with background execution.
"""

import asyncio
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from agents.api.models import (
    ErrorResponse,
    TraceResponse,
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowSummary,
)
from agents.api.store import WorkflowStore, get_store, new_workflow_id
from agents.supervisor.agent import run_workflow


app = FastAPI(
    title="Vi Agentic AI Cloud Service Fulfillment - API",
    description=(
        "HTTP layer for the Vi multi-agent SD-WAN onboarding platform. "
        "Wraps Supervisor + 8 specialist agents. See /docs for interactive use."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


def _to_summary(entry: dict) -> WorkflowSummary:
    return WorkflowSummary(
        workflow_id=entry["workflow_id"],
        customer_name=entry["customer_name"],
        status=entry["status"],
        final_decision=entry.get("final_decision"),
        started_at=entry["started_at"],
        finished_at=entry.get("finished_at"),
        duration_sec=entry.get("duration_sec"),
        site_count=entry.get("site_count", 0),
        estimated_cost_inr_monthly=entry.get("estimated_cost_inr_monthly"),
        audit_pdf_available=bool(entry.get("audit_pdf_path")),
        error=entry.get("error"),
    )


async def _execute_workflow(
    workflow_id: str,
    req: WorkflowCreateRequest,
    store: WorkflowStore,
) -> None:
    """Runs the supervisor in a thread and updates the store live."""
    loop = asyncio.get_running_loop()

    def trace_callback(wf_id: str, line: str) -> None:
        # Called from worker thread; schedule the append on the loop.
        asyncio.run_coroutine_threadsafe(
            store.append_trace(wf_id, line), loop
        )

    try:
        state = await asyncio.to_thread(
            run_workflow,
            user_request=req.user_request,
            customer_name=req.customer_name,
            deployment_mode=req.deployment_mode,
            approval_token=req.approval_token,
            workflow_id=workflow_id,
            trace_callback=trace_callback,
        )
        await store.complete(workflow_id, state)
    except Exception as e:
        await store.complete(workflow_id, {
            "error": f"{type(e).__name__}: {e}",
            "final_decision": "error",
            "audit_pdf_path": None,
        })


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "vi-agentic-platform"}


@app.post(
    "/workflows",
    response_model=WorkflowCreateResponse,
    status_code=202,
    responses={400: {"model": ErrorResponse}},
)
async def create_workflow(
    req: WorkflowCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> WorkflowCreateResponse:
    """Start a new workflow. Returns immediately with workflow_id; agents run in background."""
    if req.deployment_mode not in ("plan_only", "apply", "destroy"):
        raise HTTPException(status_code=400, detail="deployment_mode must be plan_only|apply|destroy")
    if req.deployment_mode in ("apply", "destroy") and not req.approval_token:
        raise HTTPException(
            status_code=400,
            detail=f"deployment_mode={req.deployment_mode} requires approval_token",
        )

    store = get_store()
    workflow_id = new_workflow_id()
    await store.create(workflow_id, req.customer_name, req.user_request)

    background_tasks.add_task(_execute_workflow, workflow_id, req, store)

    base = str(request.base_url).rstrip("/")
    return WorkflowCreateResponse(
        workflow_id=workflow_id,
        status="running",
        poll_url=f"{base}/workflows/{workflow_id}",
        trace_url=f"{base}/workflows/{workflow_id}/trace",
        pdf_url=f"{base}/workflows/{workflow_id}/pdf",
    )


@app.get("/workflows", response_model=list[WorkflowSummary])
async def list_workflows(limit: int = 20) -> list[WorkflowSummary]:
    """Recent workflows, newest first."""
    entries = await get_store().list_recent(limit=limit)
    return [_to_summary(e) for e in entries]


@app.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowSummary,
    responses={404: {"model": ErrorResponse}},
)
async def get_workflow(workflow_id: str) -> WorkflowSummary:
    entry = await get_store().get(workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return _to_summary(entry)


@app.get(
    "/workflows/{workflow_id}/trace",
    response_model=TraceResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_trace(workflow_id: str) -> TraceResponse:
    """Live agent trace - poll this every 500ms-1s during workflow execution."""
    entry = await get_store().get(workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return TraceResponse(
        workflow_id=workflow_id,
        status=entry["status"],
        trace=list(entry["trace"]),
        finished=entry["status"] != "running",
    )


@app.get(
    "/workflows/{workflow_id}/pdf",
    responses={404: {"model": ErrorResponse}},
)
async def get_audit_pdf(workflow_id: str):
    entry = await get_store().get(workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    pdf_path = entry.get("audit_pdf_path")
    if not pdf_path or not os.path.isfile(pdf_path):
        raise HTTPException(
            status_code=404,
            detail=f"Audit PDF not yet available for {workflow_id}",
        )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{workflow_id}.pdf",
    )
