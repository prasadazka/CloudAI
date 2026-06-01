"""
IaC Agent - generates Terraform from Architecture + Intake, self-validates.
Per agents.md §5.
"""

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import (
    ArchitectureResult,
    DiscoveryResult,
    IaCResult,
    IntakeResult,
)
from agents.iac.generator import estimate_planned_resources, write_workflow_files
from agents.iac.validator import run_terraform_validate


MAX_FIX_ATTEMPTS = 3


class IaCState(TypedDict):
    workflow_id: str
    customer_name: str
    intake: IntakeResult
    discovery: Optional[DiscoveryResult]
    architecture: Optional[ArchitectureResult]
    result: Optional[IaCResult]


def _build_diff_summary(intake: IntakeResult, planned: int) -> str:
    cities = ", ".join(s.city for s in intake.sites[:5])
    extra = f" + {len(intake.sites) - 5} more" if len(intake.sites) > 5 else ""
    return (
        f"Will create ~{planned} AWS resources for {len(intake.sites)} sites "
        f"({cities}{extra}). Includes 1 Transit Gateway, 1 central VPC, "
        f"per-site: VPC + EC2 (strongSwan) + IPsec VPN."
    )


def generate_node(state: IaCState) -> IaCState:
    intake = state["intake"]
    workflow_id = state["workflow_id"]
    customer = state["customer_name"]

    attempts = 0
    last_validation_output = ""
    last_outcome = "generation_failed"
    workflow_dir = ""
    artifacts: list = []

    while attempts < MAX_FIX_ATTEMPTS:
        attempts += 1
        try:
            workflow_dir, artifacts = write_workflow_files(
                workflow_id=workflow_id,
                customer_name=customer,
                intake=intake,
            )
        except Exception as e:
            state["result"] = IaCResult(
                status="generation_failed",
                workflow_dir="",
                artifacts=[],
                resources_planned=0,
                self_fix_attempts=attempts,
                validation_output="",
                error=f"{type(e).__name__}: {e}",
                diff_summary="Generation failed before any code was written.",
            )
            return state

        outcome, output = run_terraform_validate(workflow_dir)
        last_validation_output = output
        last_outcome = outcome

        if outcome in ("validated", "validation_skipped"):
            break
        # Else: validation_failed. For demo we don't have an LLM-driven fixer yet,
        # so further attempts re-run with the same templates. Exit loop after 1 retry.
        if attempts >= 1:
            break

    planned = estimate_planned_resources(intake)
    state["result"] = IaCResult(
        status=last_outcome,
        workflow_dir=workflow_dir,
        artifacts=artifacts,
        resources_planned=planned,
        self_fix_attempts=attempts,
        validation_output=last_validation_output,
        error=None,
        diff_summary=_build_diff_summary(intake, planned),
    )
    return state


def build_iac_graph():
    graph = StateGraph(IaCState)
    graph.add_node("generate", generate_node)
    graph.set_entry_point("generate")
    graph.add_edge("generate", END)
    return graph.compile()


def run_iac(
    workflow_id: str,
    customer_name: str,
    intake: IntakeResult,
    discovery: Optional[DiscoveryResult] = None,
    architecture: Optional[ArchitectureResult] = None,
) -> IaCResult:
    app = build_iac_graph()
    final = app.invoke({
        "workflow_id": workflow_id,
        "customer_name": customer_name,
        "intake": intake,
        "discovery": discovery,
        "architecture": architecture,
        "result": None,
    })
    return final["result"]
