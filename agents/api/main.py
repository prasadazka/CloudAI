"""
Cloud Siddhi (by Azkashine) - HTTP API.
Agentic AI cloud orchestration platform. Wraps the supervisor in async
FastAPI endpoints with background execution.
"""

import asyncio
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from datetime import datetime, timezone

from agents.api.models import (
    ApproveDeployRequest,
    ApproveDeployResponse,
    ErrorResponse,
    TraceResponse,
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowSummary,
)
from agents.api.store import WorkflowStore, get_store, new_workflow_id
from agents.audit.generator import build_audit
from agents.common.schemas import (
    ArchitectureResult, DeploymentResult, IaCResult, IntakeResult,
    PolicyResult, ValidationResult,
)
from agents.deployment.agent import EXPECTED_APPROVAL_TOKEN, run_deployment
from agents.iac.generator import write_workflow_files
from agents.supervisor.agent import run_workflow
from agents.validation.agent import run_validation


# When state is loaded from persisted JSON, Pydantic models become plain dicts.
# Rehydrate them back to the typed objects so downstream agents (validation,
# audit) can use attribute access (e.g. architecture.options).
_REHYDRATE_MAP = {
    "intake": IntakeResult,
    "policy": PolicyResult,
    "architecture": ArchitectureResult,
    "iac": IaCResult,
    "deployment": DeploymentResult,
    "validation": ValidationResult,
}


def _rehydrate_state(state: dict) -> dict:
    """In-place rehydrate known fields if they were JSON-round-tripped to dicts."""
    if not state:
        return state
    for key, cls in _REHYDRATE_MAP.items():
        val = state.get(key)
        if isinstance(val, dict):
            try:
                state[key] = cls(**val)
            except Exception:
                # Schema drift - leave as dict, caller can defensively check
                pass
    return state


app = FastAPI(
    title="Cloud Siddhi — Agentic Orchestration API",
    description=(
        "Agentic AI cloud orchestration platform by Azkashine. HTTP layer "
        "for the multi-agent SD-WAN onboarding pipeline. Wraps Supervisor "
        "+ 8 specialist agents. See /docs for interactive use."
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


def _apply_overrides(intake, overrides) -> dict:
    """
    Mutate the intake object in-place with user-supplied overrides.
    Returns a dict describing what changed (for the audit trail).
    """
    if not overrides:
        return {}
    changes: dict = {}

    if overrides.connectivity_type and overrides.connectivity_type != intake.connectivity_type:
        changes["connectivity_type"] = (intake.connectivity_type, overrides.connectivity_type)
        intake.connectivity_type = overrides.connectivity_type

    if overrides.compliance_tier and overrides.compliance_tier != intake.compliance_tier:
        changes["compliance_tier"] = (intake.compliance_tier, overrides.compliance_tier)
        intake.compliance_tier = overrides.compliance_tier

    if overrides.qos_apps is not None:
        changes["qos_apps"] = (list(intake.qos_apps), list(overrides.qos_apps))
        intake.qos_apps = list(overrides.qos_apps)

    if overrides.sites:
        # Match overrides by city (case-insensitive). Multi-occurrence: positional.
        site_changes = []
        bw_map: dict[str, int] = {}
        for so in overrides.sites:
            if so.bandwidth_mbps is not None:
                bw_map.setdefault(so.city.strip().lower(), so.bandwidth_mbps)
        for s in intake.sites:
            new_bw = bw_map.get(s.city.strip().lower())
            if new_bw is not None and new_bw != s.bandwidth_mbps:
                site_changes.append({"city": s.city, "from": s.bandwidth_mbps, "to": new_bw})
                s.bandwidth_mbps = new_bw
        if site_changes:
            changes["sites"] = site_changes

    return changes


async def _execute_deploy_phase(
    workflow_id: str,
    workflow_dir: str,
    mode: str,
    approval_token: str,
    store: WorkflowStore,
    overrides=None,
) -> None:
    """Runs apply/destroy on existing IaC artifacts. Appends events to same workflow."""
    loop = asyncio.get_running_loop()

    def append(line: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        asyncio.run_coroutine_threadsafe(
            store.append_trace(workflow_id, f"[{ts}] {line}"), loop
        )

    # 0. If user supplied overrides, mutate intake + regenerate IaC before apply.
    if mode == "apply" and overrides:
        entry = await store.get(workflow_id)
        state = _rehydrate_state((entry or {}).get("state") or {})
        intake = state.get("intake")
        if intake is not None:
            changes = _apply_overrides(intake, overrides)
            if changes:
                append(f"User overrides applied: {sorted(changes.keys())}")
                for k, v in changes.items():
                    if k == "sites":
                        for sc in v:
                            append(
                                f"  · {sc['city']}: bandwidth {sc['from']} → {sc['to']} Mbps"
                            )
                    else:
                        append(f"  · {k}: {v[0]} → {v[1]}")

                customer = (entry or {}).get("customer_name") or "Unnamed Customer"
                try:
                    _, _artifacts = write_workflow_files(
                        workflow_id=workflow_id,
                        customer_name=customer,
                        intake=intake,
                    )
                    append(f"IaC regenerated with overrides — {len(_artifacts)} files")
                except Exception as e:
                    append(f"IaC regeneration failed: {type(e).__name__}: {e}")

    # Read actual site count from intake to make messages truthful
    entry0 = await store.get(workflow_id)
    state0 = _rehydrate_state((entry0 or {}).get("state") or {})
    intake0 = state0.get("intake")
    site_count = getattr(intake0, "site_count", 0) if intake0 else 0

    if site_count <= 0:
        typical = "a few minutes"
    elif site_count <= 2:
        typical = "5-7 min"
    elif site_count <= 5:
        typical = "8-12 min"
    else:
        typical = "15-25 min"

    append(f"Approval received — starting {mode.upper()} phase")
    append(f"Supervisor: routing to Deployment Agent ({mode} mode)")

    # Heartbeat task: append a progress line every 30s while terraform runs
    stop_heartbeat = asyncio.Event()

    async def heartbeat():
        seconds = 0
        while not stop_heartbeat.is_set():
            try:
                await asyncio.wait_for(stop_heartbeat.wait(), timeout=30)
                return
            except asyncio.TimeoutError:
                seconds += 30
                mins = seconds // 60
                rem = seconds % 60
                clock = f"{mins}m{rem:02d}s" if mins else f"{rem}s"
                action = "terraform apply" if mode == "apply" else "terraform destroy"
                site_text = (
                    f"{site_count} site{'s' if site_count != 1 else ''}"
                    if site_count > 0
                    else "your infra"
                )
                append(
                    f"Deployment: {action} in progress — {clock} elapsed "
                    f"(typical: {typical} for {site_text})"
                )

    hb_task = asyncio.create_task(heartbeat())

    # Forward each terraform stdout line to the trace, filtering noise.
    _TF_NOISE = (
        "Reading...", "Refreshing state...", "Read complete",
        "Initializing", "Installing", "Finding", "Downloading",
    )

    def stream_tf_line(line: str) -> None:
        s = line.strip()
        if not s:
            return
        if any(noise in s for noise in _TF_NOISE):
            return
        # Highlight key events
        if "Creation complete" in s or "Destruction complete" in s:
            append(f"  ✓ {s}")
        elif "Creating..." in s or "Destroying..." in s or "Still" in s:
            append(f"  ⏳ {s}")
        elif "Error" in s or "error" in s.lower():
            append(f"  ✗ {s}")
        elif s.startswith("Plan:") or s.startswith("Apply complete"):
            append(s)

    try:
        # 1. Run real deployment with live streaming
        result = await asyncio.to_thread(
            run_deployment,
            workflow_id=workflow_id,
            workflow_dir=workflow_dir,
            mode=mode,
            approval_token=approval_token,
            line_callback=stream_tf_line,
        )
        stop_heartbeat.set()
        await hb_task

        await store.patch_state_field(workflow_id, "deployment", result)
        append(f"Deployment: {result.status} - {result.summary}")

        # 2. If apply succeeded, re-run validation (now potentially against real infra)
        if mode == "apply" and result.status in ("applied", "applied_with_warnings"):
            append("Supervisor: routing to Validation Agent")
            entry = await store.get(workflow_id)
            state = _rehydrate_state((entry or {}).get("state") or {})
            validation = await asyncio.to_thread(
                run_validation,
                intake=state.get("intake"),
                architecture=state.get("architecture"),
                deployment=result,
                progress_callback=lambda msg: append(msg),
            )
            await store.patch_state_field(workflow_id, "validation", validation)
            append(
                f"Validation: {validation.status} - "
                f"{validation.sites_passed} pass, "
                f"{validation.sites_borderline} borderline, "
                f"{validation.sites_failed} failed "
                f"(of {validation.sites_tested} sites)"
            )

            # Re-collect inventory NOW that SSM-wait gave tunnels time to come
            # up. The first collect (inside deploy agent) often catches IPsec
            # mid-negotiation and shows DOWN. This second pass overwrites with
            # the steady-state truth that the PDF will render.
            try:
                from agents.deployment.inventory import collect_infrastructure
                fresh_infra = await asyncio.to_thread(
                    collect_infrastructure, workflow_id=workflow_id
                )
                result.infrastructure = fresh_infra
                await store.patch_state_field(workflow_id, "deployment", result)
                # At least one tunnel UP per VPN = site reachable. AWS provides
                # two tunnels for HA but our strongSwan deliberately uses one
                # active to avoid xfrm policy collision (no BGP).
                up_count = sum(
                    1 for s in fresh_infra.sites
                    if s.tunnel_1_status == "UP" or s.tunnel_2_status == "UP"
                )
                append(
                    f"Inventory refreshed: {fresh_infra.total_resources} resources, "
                    f"{up_count}/{len(fresh_infra.sites)} sites reachable (at least one tunnel UP)"
                )
            except Exception as e:  # noqa: BLE001
                append(f"Inventory refresh skipped: {type(e).__name__}: {e}")

        # 3. Generate the FINAL audit PDF (apply only — destroy keeps the original)
        if mode == "apply" and result.status in ("applied", "applied_with_warnings"):
            append("Supervisor: routing to Audit Agent")
            try:
                entry = await store.get(workflow_id)
                state = _rehydrate_state((entry or {}).get("state") or {})
                pdf_path = await asyncio.to_thread(
                    build_audit,
                    intake=state.get("intake"),
                    policy=state.get("policy"),
                    customer_name=(entry or {}).get("customer_name") or "Unnamed Customer",
                    output_dir="audits",
                    architecture=state.get("architecture"),
                    deployment=state.get("deployment"),
                    validation=state.get("validation"),
                    workflow_id=workflow_id,
                    approval_signoff=f"NOC approved + {mode.upper()} executed",
                )
                # Persist the audit_pdf_path back on the entry so /pdf works.
                async with store._lock:  # type: ignore[attr-defined]
                    e2 = store._data.get(workflow_id)  # type: ignore[attr-defined]
                    if e2 is not None:
                        e2["audit_pdf_path"] = pdf_path
                append(f"Audit: final compliance PDF generated")
            except Exception as e:
                append(f"Audit PDF generation failed: {type(e).__name__}: {e}")

        # 4. Final phase status
        if result.status in ("applied", "applied_with_warnings"):
            await store.set_phase(workflow_id, "deployed")
            append("Phase complete: infrastructure DEPLOYED")
        elif result.status == "destroyed":
            await store.set_phase(workflow_id, "destroyed")
            append("Phase complete: infrastructure DESTROYED")
        elif result.status == "apply_failed" and getattr(result, "rollback_triggered", False):
            # Apply failed but auto-rollback succeeded - leave in "errored"
            # so user can re-trigger but make the trace clear
            await store.set_phase(workflow_id, "errored")
            append("Phase complete: APPLY FAILED, partial state auto-cleaned")
        else:
            await store.set_phase(workflow_id, "errored")
            append(f"Phase ended with status: {result.status}")
    except Exception as e:
        stop_heartbeat.set()
        if not hb_task.done():
            await hb_task
        append(f"DEPLOYMENT ERROR: {type(e).__name__}: {e}")
        await store.set_phase(workflow_id, "errored")


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
    TERMINAL = {"completed", "deployed", "destroyed", "errored", "awaiting_approval"}
    return TraceResponse(
        workflow_id=workflow_id,
        status=entry["status"],
        trace=list(entry["trace"]),
        finished=entry["status"] in TERMINAL,
    )


@app.post(
    "/workflows/{workflow_id}/adopt",
    status_code=201,
    responses={400: {"model": ErrorResponse}},
)
async def adopt_workflow(workflow_id: str, body: dict) -> dict:
    """
    Re-attach a previously-deployed workflow whose IaC dir still exists on disk
    after the API process was restarted. Marks it 'deployed' so /deploy can
    re-apply (e.g. after a module template fix that needs EC2 replacement).
    Body: {"customer_name": str, "workflow_dir": str}.
    """
    customer_name = body.get("customer_name") or "Adopted Workflow"
    workflow_dir = body.get("workflow_dir")
    if not workflow_dir or not os.path.isdir(workflow_dir):
        raise HTTPException(status_code=400, detail=f"workflow_dir not found: {workflow_dir}")

    store = get_store()
    await store.create(workflow_id, customer_name, "(adopted - request not preserved)")

    async with store._lock:  # type: ignore[attr-defined]
        e = store._data[workflow_id]  # type: ignore[attr-defined]
        # Use a dict (not a class instance) so it round-trips through JSON
        # persistence cleanly; the deploy endpoint's getattr/get fallback
        # accepts either shape.
        e["state"] = {
            "iac": {"workflow_dir": workflow_dir},
            "deployment_mode": "apply",
        }
        e["trace"].append(f"[adopted] Workflow re-attached from {workflow_dir}")

    # set_phase persists to disk - so a restart after adopt remembers the state
    await store.set_phase(workflow_id, "deployed")
    return {"workflow_id": workflow_id, "status": "deployed", "workflow_dir": workflow_dir}


@app.post(
    "/workflows/{workflow_id}/deploy",
    response_model=ApproveDeployResponse,
    status_code=202,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def approve_and_deploy(
    workflow_id: str,
    body: ApproveDeployRequest,
    background_tasks: BackgroundTasks,
) -> ApproveDeployResponse:
    """
    Human-in-the-loop approval gate. Triggers real terraform apply/destroy
    on the IaC artifacts already generated by the previous plan_only run.

    Required: a workflow in `awaiting_approval` or `deployed` state, plus
    the correct approval_token.
    """
    if body.mode not in ("apply", "destroy"):
        raise HTTPException(status_code=400, detail="mode must be apply or destroy")
    if body.approval_token != EXPECTED_APPROVAL_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Invalid approval token. Use NOC-APPROVED-V1.",
        )

    store = get_store()
    entry = await store.get(workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    # "errored" is included so users can retry an apply that failed partway
    # (e.g. validation error) without having to re-run plan_only from scratch.
    allowed = {"awaiting_approval", "deployed", "errored"}
    if body.mode == "apply" and entry["status"] not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow status {entry['status']} not approvable. Expected one of {sorted(allowed)}.",
        )
    if body.mode == "destroy" and entry["status"] not in {"deployed", "errored"}:
        raise HTTPException(
            status_code=400,
            detail="Workflow must be deployed before destroying.",
        )

    state = entry.get("state") or {}
    iac = state.get("iac")
    if not iac:
        raise HTTPException(status_code=400, detail="No IaC artifacts in this workflow")
    workflow_dir = getattr(iac, "workflow_dir", None) or iac.get("workflow_dir")
    if not workflow_dir:
        raise HTTPException(status_code=400, detail="IaC workflow_dir missing")

    new_phase = "applying" if body.mode == "apply" else "destroying"
    await store.set_phase(workflow_id, new_phase)

    background_tasks.add_task(
        _execute_deploy_phase,
        workflow_id,
        workflow_dir,
        body.mode,
        body.approval_token,
        store,
        body.overrides,
    )

    return ApproveDeployResponse(
        workflow_id=workflow_id,
        status=new_phase,
        mode=body.mode,
        message=f"{body.mode.upper()} phase started. Poll /trace for progress.",
    )


@app.get(
    "/workflows/{workflow_id}/full",
    responses={404: {"model": ErrorResponse}},
)
async def get_full_workflow(workflow_id: str) -> dict:
    """Full serialized agent results - enables rich UI detail panels."""
    entry = await get_store().get(workflow_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    def serialize(obj):
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        return obj

    state = entry.get("state") or {}
    return {
        "workflow_id": workflow_id,
        "status": entry["status"],
        "customer_name": entry["customer_name"],
        "user_request": entry["user_request"],
        "final_decision": entry.get("final_decision"),
        "audit_pdf_available": bool(entry.get("audit_pdf_path")),
        "intake": serialize(state.get("intake")),
        "discovery": serialize(state.get("discovery")),
        "policy": serialize(state.get("policy")),
        "architecture": serialize(state.get("architecture")),
        "iac": serialize(state.get("iac")),
        "deployment": serialize(state.get("deployment")),
        "validation": serialize(state.get("validation")),
    }


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
