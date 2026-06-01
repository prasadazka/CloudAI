"""
Supervisor Agent - orchestrates Intake -> Policy -> Audit.
Uses LangGraph state machine with conditional routing.
"""

import uuid
from datetime import datetime, timezone
from typing import Callable, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.architecture.agent import run_architecture
from agents.audit.generator import build_audit
from agents.common.schemas import (
    ArchitectureResult,
    DeploymentMode,
    DeploymentResult,
    DiscoveryResult,
    IaCResult,
    IntakeResult,
    PolicyResult,
    ValidationResult,
)
from agents.deployment.agent import run_deployment
from agents.discovery.agent import run_discovery
from agents.iac.agent import run_iac
from agents.intake.agent import run_intake
from agents.policy.agent import run_policy
from agents.validation.agent import run_validation


FinalDecision = Literal[
    "clarification_needed",
    "rejected",
    "approved_auto",
    "approved_with_escalation",
    "error",
]


TraceCallback = Callable[[str, str], None]


class SupervisorState(TypedDict):
    user_request: str
    customer_name: str
    workflow_id: str
    deployment_mode: DeploymentMode
    approval_token: Optional[str]
    intake: Optional[IntakeResult]
    discovery: Optional[DiscoveryResult]
    policy: Optional[PolicyResult]
    architecture: Optional[ArchitectureResult]
    iac: Optional[IaCResult]
    deployment: Optional[DeploymentResult]
    validation: Optional[ValidationResult]
    audit_pdf_path: Optional[str]
    final_decision: Optional[FinalDecision]
    clarification_question: Optional[str]
    error: Optional[str]
    trace: list[str]
    trace_callback: Optional[TraceCallback]


def _log(state: SupervisorState, message: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {message}"
    state["trace"].append(line)
    cb = state.get("trace_callback")
    if cb:
        try:
            cb(state["workflow_id"], line)
        except Exception:
            pass


def intake_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Intake Agent")
    try:
        result = run_intake(state["user_request"])
        state["intake"] = result
        _log(
            state,
            f"Intake: {result.site_count} sites extracted, "
            f"confidence={result.confidence:.2f}, "
            f"clarification={'YES' if result.needs_clarification else 'NO'}",
        )
    except Exception as e:
        state["error"] = f"Intake failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Intake ERROR: {e}")
    return state


def discovery_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Discovery Agent")
    try:
        result = run_discovery(state["intake"], state["customer_name"])
        state["discovery"] = result
        savings_l = result.total_estimated_savings_inr_monthly / 1_00_000
        _log(
            state,
            f"Discovery: customer_found={result.customer_found}, "
            f"{len(result.existing_resources)} existing resources, "
            f"{len(result.recommendations)} recommendations, "
            f"savings=Rs {savings_l:.2f}L/month",
        )
    except Exception as e:
        state["error"] = f"Discovery failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Discovery ERROR: {e}")
    return state


def policy_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Policy Agent")
    try:
        result = run_policy(state["intake"])
        state["policy"] = result
        _log(
            state,
            f"Policy: {result.overall_status} "
            f"(level={result.approval_level_required}, "
            f"cost=Rs {result.estimated_cost_inr_monthly/1_00_000:.2f}L/month)",
        )
    except Exception as e:
        state["error"] = f"Policy failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Policy ERROR: {e}")
    return state


def architecture_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Architecture Agent")
    try:
        result = run_architecture(state["intake"], state.get("discovery"))
        state["architecture"] = result
        chosen = next(o for o in result.options if o.recommended)
        _log(
            state,
            f"Architecture: {len(result.options)} options designed, "
            f"recommending '{result.recommended_option_name}' "
            f"(Rs {chosen.cost_inr_monthly/1_00_000:.2f}L/month, "
            f"SLA {chosen.sla_uptime_pct}%, "
            f"resilience {chosen.resilience_score}/10)",
        )
    except Exception as e:
        state["error"] = f"Architecture failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Architecture ERROR: {e}")
    return state


def iac_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to IaC Agent")
    try:
        result = run_iac(
            workflow_id=state["workflow_id"],
            customer_name=state["customer_name"],
            intake=state["intake"],
            discovery=state.get("discovery"),
            architecture=state.get("architecture"),
        )
        state["iac"] = result
        _log(
            state,
            f"IaC: {result.status} - "
            f"{len(result.artifacts)} files generated, "
            f"~{result.resources_planned} resources planned, "
            f"fix_attempts={result.self_fix_attempts}",
        )
        if result.status not in ("validated", "validation_skipped"):
            state["error"] = f"IaC failed: {result.error or 'validation'}"
    except Exception as e:
        state["error"] = f"IaC failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"IaC ERROR: {e}")
    return state


def deployment_node(state: SupervisorState) -> SupervisorState:
    iac = state.get("iac")
    if not iac or not iac.workflow_dir:
        _log(state, "Supervisor: skipping Deployment (no IaC workflow_dir)")
        return state
    _log(state, f"Supervisor: routing to Deployment Agent (mode={state['deployment_mode']})")
    try:
        result = run_deployment(
            workflow_id=state["workflow_id"],
            workflow_dir=iac.workflow_dir,
            mode=state["deployment_mode"],
            approval_token=state.get("approval_token"),
            iac=iac,
        )
        state["deployment"] = result
        _log(state, f"Deployment: {result.status} - {result.summary}")
    except Exception as e:
        state["error"] = f"Deployment failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Deployment ERROR: {e}")
    return state


def validation_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Validation Agent")
    try:
        result = run_validation(
            intake=state["intake"],
            architecture=state.get("architecture"),
            deployment=state.get("deployment"),
        )
        state["validation"] = result
        _log(
            state,
            f"Validation: {result.status} (mode={result.mode}) - "
            f"{result.sites_passed}/{result.sites_tested} pass, "
            f"{result.sites_borderline} borderline, {result.sites_failed} failed",
        )
    except Exception as e:
        state["error"] = f"Validation failed: {type(e).__name__}: {e}"
        _log(state, f"Validation ERROR: {e}")
    return state


def audit_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: routing to Audit Agent for PDF generation")
    try:
        pdf_path = build_audit(
            intake=state["intake"],
            policy=state["policy"],
            customer_name=state["customer_name"],
            output_dir="audits",
            approval_signoff=None,
            architecture=state.get("architecture"),
            deployment=state.get("deployment"),
            validation=state.get("validation"),
            workflow_id=state["workflow_id"],
        )
        state["audit_pdf_path"] = pdf_path
        _log(state, f"Audit: PDF generated -> {pdf_path}")

        pol = state["policy"]
        if pol.overall_status == "rejected":
            state["final_decision"] = "rejected"
        elif pol.overall_status == "approved":
            state["final_decision"] = "approved_auto"
        else:
            state["final_decision"] = "approved_with_escalation"
    except Exception as e:
        state["error"] = f"Audit failed: {type(e).__name__}: {e}"
        state["final_decision"] = "error"
        _log(state, f"Audit ERROR: {e}")
    return state


def clarification_node(state: SupervisorState) -> SupervisorState:
    _log(state, "Supervisor: returning clarification request to user")
    state["clarification_question"] = state["intake"].clarification_question
    state["final_decision"] = "clarification_needed"
    return state


def _after_intake(state: SupervisorState) -> str:
    if state.get("error"):
        return "end"
    if state["intake"].needs_clarification:
        return "clarification"
    return "discovery"


def _after_discovery(state: SupervisorState) -> str:
    if state.get("error"):
        return "end"
    return "policy"


def _after_policy(state: SupervisorState) -> str:
    if state.get("error"):
        return "end"
    if state["policy"].overall_status == "rejected":
        return "audit"
    return "architecture"


def _after_architecture(state: SupervisorState) -> str:
    if state.get("error"):
        return "end"
    return "iac"


def _after_iac(state: SupervisorState) -> str:
    if state.get("error"):
        return "audit"
    return "deployment"


def _after_deployment(state: SupervisorState) -> str:
    return "validation"


def _after_validation(state: SupervisorState) -> str:
    return "audit"  # always produce audit PDF


def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("run_intake", intake_node)
    graph.add_node("run_discovery", discovery_node)
    graph.add_node("run_policy", policy_node)
    graph.add_node("run_architecture", architecture_node)
    graph.add_node("run_iac", iac_node)
    graph.add_node("run_deployment", deployment_node)
    graph.add_node("run_validation", validation_node)
    graph.add_node("run_audit", audit_node)
    graph.add_node("ask_clarification", clarification_node)

    graph.set_entry_point("run_intake")

    graph.add_conditional_edges(
        "run_intake",
        _after_intake,
        {
            "discovery": "run_discovery",
            "clarification": "ask_clarification",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "run_discovery",
        _after_discovery,
        {"policy": "run_policy", "end": END},
    )
    graph.add_conditional_edges(
        "run_policy",
        _after_policy,
        {
            "architecture": "run_architecture",
            "audit": "run_audit",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "run_architecture",
        _after_architecture,
        {"iac": "run_iac", "audit": "run_audit", "end": END},
    )
    graph.add_conditional_edges(
        "run_iac",
        _after_iac,
        {"deployment": "run_deployment", "audit": "run_audit", "end": END},
    )
    graph.add_conditional_edges(
        "run_deployment",
        _after_deployment,
        {"validation": "run_validation"},
    )
    graph.add_conditional_edges(
        "run_validation",
        _after_validation,
        {"audit": "run_audit"},
    )
    graph.add_edge("run_audit", END)
    graph.add_edge("ask_clarification", END)

    return graph.compile()


def run_workflow(
    user_request: str,
    customer_name: str = "Unnamed Customer",
    deployment_mode: DeploymentMode = "plan_only",
    approval_token: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_callback: Optional[TraceCallback] = None,
) -> SupervisorState:
    """
    End-to-end: NL request -> final decision + PDF + trace.

    deployment_mode controls what the Deployment Agent does:
      - "plan_only" (default): terraform init + plan. Zero AWS cost. Safe.
      - "apply": terraform apply. Requires approval_token='NOC-APPROVED-V1'.
                 Will create real AWS resources (~Rs 13/hr until destroyed).
      - "destroy": terraform destroy. Requires approval_token.
    """
    if not workflow_id:
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    initial: SupervisorState = {
        "user_request": user_request,
        "customer_name": customer_name,
        "workflow_id": workflow_id,
        "deployment_mode": deployment_mode,
        "approval_token": approval_token,
        "intake": None,
        "discovery": None,
        "policy": None,
        "architecture": None,
        "iac": None,
        "deployment": None,
        "validation": None,
        "audit_pdf_path": None,
        "final_decision": None,
        "clarification_question": None,
        "error": None,
        "trace": [f"[start] Workflow {workflow_id} initiated (deploy={deployment_mode})"],
        "trace_callback": trace_callback,
    }
    if trace_callback:
        try:
            trace_callback(workflow_id, initial["trace"][0])
        except Exception:
            pass
    app = build_supervisor_graph()
    return app.invoke(initial)
