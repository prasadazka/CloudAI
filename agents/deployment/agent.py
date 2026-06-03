"""
Deployment Agent - executes Terraform apply/plan/destroy.
Per agents.md §6.

Safe by default: requires explicit approval_token to perform apply.
"""

from typing import Callable, Optional, TypedDict

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
from agents.deployment.inventory import collect_infrastructure


# Approval token format: caller must supply this exact value to actually apply.
EXPECTED_APPROVAL_TOKEN = "NOC-APPROVED-V1"


class DeploymentState(TypedDict):
    workflow_id: str
    workflow_dir: str
    mode: DeploymentMode
    approval_token: Optional[str]
    iac: Optional[IaCResult]
    result: Optional[DeploymentResult]
    line_callback: Optional[Callable[[str], None]]


def _build_sites_detail(
    stdout: str, mode: str, exit_code: int = 0
) -> list[SiteDeployment]:
    """
    Classify each site's outcome from terraform stdout.

    Note: terraform reports every resource as "Creating..." then
    "Creation complete". We can't reliably pair these per resource, so we
    rely on the overall terraform exit code + presence of completion events.
    """
    per_site = parse_per_site_status(stdout)
    out: list[SiteDeployment] = []
    for site_name, data in per_site.items():
        if mode == "plan_only":
            status = "pending"
        elif data.get("failed", 0) > 0:
            status = "failed"
        elif exit_code == 0 and data.get("created", 0) > 0:
            # terraform succeeded overall AND we saw creation events for this
            # site -> the site's resources are up
            status = "succeeded"
        elif exit_code != 0 and data.get("created", 0) > 0:
            # terraform failed overall but this site's resources got created
            # before the failure -> mark created (will need teardown)
            status = "creating"
        else:
            status = "pending"
        out.append(SiteDeployment(site_name=site_name, status=status))
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
        apply = terraform_apply(workflow_dir, line_callback=state.get("line_callback"))
        sites_detail = _build_sites_detail(apply.stdout, mode, apply.exit_code)
        succeeded = sum(1 for s in sites_detail if s.status == "succeeded")
        failed = sum(1 for s in sites_detail if s.status == "failed")

        if apply.exit_code == 0:
            status = "applied" if failed == 0 else "applied_with_warnings"
        else:
            status = "apply_failed"

        # Post-apply: enumerate exactly what's now in AWS. Non-fatal on failure.
        infra = None
        if status in ("applied", "applied_with_warnings"):
            try:
                infra = collect_infrastructure(workflow_id=state.get("workflow_id"))
            except Exception as e:  # noqa: BLE001
                infra = None
                # best-effort - we still want the deployment result back

        # Auto-rollback: apply failed AND some resources got created -> destroy
        # them so we don't leak orphans into AWS quota. Without this, every
        # failed apply leaves IGWs/VPCs/IAM behind that block the next run.
        rolled_back = False
        rollback_notes = ""
        if status == "apply_failed":
            try:
                cb = state.get("line_callback")
                if cb:
                    cb("ROLLBACK: apply failed - running terraform destroy to clean partial state")
                rb = terraform_destroy(workflow_dir, line_callback=cb)
                if rb.exit_code == 0:
                    rolled_back = True
                    rollback_notes = "auto-rollback succeeded - partial resources destroyed"
                    if cb:
                        cb("ROLLBACK: cleanup complete - AWS state restored")
                else:
                    rollback_notes = (
                        f"auto-rollback failed (terraform destroy exit {rb.exit_code}) - "
                        "manual cleanup likely required via scripts/nuke-videmo-aws.ps1"
                    )
                    if cb:
                        cb(f"ROLLBACK FAILED: {rollback_notes}")
            except Exception as e:  # noqa: BLE001
                rollback_notes = f"auto-rollback errored: {type(e).__name__}: {e}"

        # Mark per-site detail as rolled_back when rollback succeeded so the UI
        # tells the truth (resources are gone, not still "creating").
        if rolled_back:
            sites_detail = [
                SiteDeployment(site_name=s.site_name, status="rolled_back")
                for s in sites_detail
            ]
            succeeded = 0
            failed = 0

        summary_text = (
            f"Apply {'succeeded' if status == 'applied' else status}: "
            f"{succeeded}/{len(sites_detail)} sites operational"
        )
        if rollback_notes:
            summary_text += f" | {rollback_notes}"

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
            rollback_triggered=rolled_back,
            summary=summary_text,
            infrastructure=infra,
        )
        return state

    if mode == "destroy":
        destroy = terraform_destroy(workflow_dir, line_callback=state.get("line_callback"))
        sites_detail = _build_sites_detail(destroy.stdout, mode, destroy.exit_code)
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
    line_callback: Optional[Callable[[str], None]] = None,
) -> DeploymentResult:
    app = build_deployment_graph()
    final = app.invoke({
        "workflow_id": workflow_id,
        "workflow_dir": workflow_dir,
        "mode": mode,
        "approval_token": approval_token,
        "iac": iac,
        "result": None,
        "line_callback": line_callback,
    })
    return final["result"]
