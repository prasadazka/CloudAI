"""
Deployment Agent - executes Terraform apply/plan/destroy.
Per agents.md §6.

Safe by default: requires explicit approval_token to perform apply.
"""

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import (
    DeploymentMode,
    DeploymentResult,
    IaCResult,
    SiteDeployment,
)
from agents.deployment.executor import (
    have_terraform,
    parse_per_site_status,
    parse_plan_summary,
    tail,
    terraform_apply,
    terraform_destroy,
    terraform_init,
    terraform_plan,
)


# Approval token format: caller must supply this exact value to actually apply.
EXPECTED_APPROVAL_TOKEN = "NOC-APPROVED-V1"


class DeploymentState(TypedDict):
    workflow_id: str
    workflow_dir: str
    mode: DeploymentMode
    approval_token: Optional[str]
    iac: Optional[IaCResult]
    result: Optional[DeploymentResult]


def _build_sites_detail(stdout: str, mode: str) -> list[SiteDeployment]:
    per_site = parse_per_site_status(stdout)
    out: list[SiteDeployment] = []
    for site_name, data in per_site.items():
        if mode == "plan_only":
            status = "pending"
        elif data["created"] > 0 and data["in_progress"] == 0 and data["failed"] == 0:
            status = "succeeded"
        elif data["failed"] > 0:
            status = "failed"
        else:
            status = "creating"
        out.append(SiteDeployment(
            site_name=site_name,
            status=status,
        ))
    return out


def deploy_node(state: DeploymentState) -> DeploymentState:
    mode = state["mode"]
    workflow_dir = state["workflow_dir"]
    approval = state.get("approval_token")

    if not have_terraform():
        state["result"] = DeploymentResult(
            mode=mode,
            status="skipped_no_terraform",
            workflow_dir=workflow_dir,
            summary="terraform binary not on PATH - deployment skipped",
        )
        return state

    # Enforce approval gate for destructive modes
    if mode in ("apply", "destroy") and approval != EXPECTED_APPROVAL_TOKEN:
        state["result"] = DeploymentResult(
            mode=mode,
            status="skipped_no_approval",
            workflow_dir=workflow_dir,
            approval_token=approval,
            summary=(
                f"{mode.upper()} requires approval_token='{EXPECTED_APPROVAL_TOKEN}'. "
                f"Got: {'<none>' if not approval else approval}"
            ),
        )
        return state

    # Always init first
    init = terraform_init(workflow_dir)
    if init.exit_code != 0:
        state["result"] = DeploymentResult(
            mode=mode,
            status="plan_failed" if mode == "plan_only" else "apply_failed",
            workflow_dir=workflow_dir,
            terraform_output_tail=tail(init.stdout + "\n" + init.stderr),
            summary=f"terraform init failed (exit {init.exit_code})",
        )
        return state

    if mode == "plan_only":
        plan = terraform_plan(workflow_dir)
        # exit codes for plan: 0 = no changes, 1 = error, 2 = changes present
        if plan.exit_code not in (0, 2):
            state["result"] = DeploymentResult(
                mode=mode,
                status="plan_failed",
                workflow_dir=workflow_dir,
                total_duration_sec=plan.duration_sec,
                terraform_output_tail=tail(plan.stdout + "\n" + plan.stderr),
                summary=f"terraform plan failed (exit {plan.exit_code})",
            )
            return state

        to_add, to_change, to_destroy = parse_plan_summary(plan.stdout)
        state["result"] = DeploymentResult(
            mode=mode,
            status="plan_succeeded",
            workflow_dir=workflow_dir,
            sites_total=len(_build_sites_detail(plan.stdout, mode)),
            sites_detail=_build_sites_detail(plan.stdout, mode),
            total_duration_sec=plan.duration_sec,
            terraform_output_tail=tail(plan.stdout),
            summary=(
                f"Plan: {to_add} to add, {to_change} to change, "
                f"{to_destroy} to destroy"
            ),
        )
        return state

    if mode == "apply":
        apply = terraform_apply(workflow_dir)
        sites_detail = _build_sites_detail(apply.stdout, mode)
        succeeded = sum(1 for s in sites_detail if s.status == "succeeded")
        failed = sum(1 for s in sites_detail if s.status == "failed")

        if apply.exit_code == 0:
            status = "applied" if failed == 0 else "applied_with_warnings"
        else:
            status = "apply_failed"

        state["result"] = DeploymentResult(
            mode=mode,
            status=status,
            workflow_dir=workflow_dir,
            sites_total=len(sites_detail),
            sites_succeeded=succeeded,
            sites_failed=failed,
            sites_detail=sites_detail,
            total_duration_sec=apply.duration_sec,
            terraform_output_tail=tail(apply.stdout + "\n" + apply.stderr),
            approval_token=approval,
            summary=(
                f"Apply {'succeeded' if status == 'applied' else status}: "
                f"{succeeded}/{len(sites_detail)} sites operational"
            ),
        )
        return state

    if mode == "destroy":
        destroy = terraform_destroy(workflow_dir)
        sites_detail = _build_sites_detail(destroy.stdout, mode)
        status = "destroyed" if destroy.exit_code == 0 else "destroy_failed"
        state["result"] = DeploymentResult(
            mode=mode,
            status=status,
            workflow_dir=workflow_dir,
            sites_total=len(sites_detail),
            sites_detail=sites_detail,
            total_duration_sec=destroy.duration_sec,
            terraform_output_tail=tail(destroy.stdout + "\n" + destroy.stderr),
            approval_token=approval,
            summary=(
                f"Destroy {'completed' if status == 'destroyed' else 'failed'}"
            ),
        )
        return state

    state["result"] = DeploymentResult(
        mode=mode,
        status="plan_failed",
        workflow_dir=workflow_dir,
        summary=f"Unknown mode: {mode}",
    )
    return state


def build_deployment_graph():
    graph = StateGraph(DeploymentState)
    graph.add_node("deploy", deploy_node)
    graph.set_entry_point("deploy")
    graph.add_edge("deploy", END)
    return graph.compile()


def run_deployment(
    workflow_id: str,
    workflow_dir: str,
    mode: DeploymentMode = "plan_only",
    approval_token: Optional[str] = None,
    iac: Optional[IaCResult] = None,
) -> DeploymentResult:
    app = build_deployment_graph()
    final = app.invoke({
        "workflow_id": workflow_id,
        "workflow_dir": workflow_dir,
        "mode": mode,
        "approval_token": approval_token,
        "iac": iac,
        "result": None,
    })
    return final["result"]
