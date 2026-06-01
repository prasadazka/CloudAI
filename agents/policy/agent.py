from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import IntakeResult, PolicyResult
from agents.policy.rules import (
    ALL_CHECKS,
    decide_approval_level,
    estimate_total_cost,
)


class PolicyState(TypedDict):
    intake: IntakeResult
    result: PolicyResult | None


def _summary_line(
    overall: str, approval: str, cost_lakhs: float, n_sites: int
) -> str:
    if overall == "rejected":
        return (
            f"REJECTED: blocking violation for {n_sites} site request "
            f"(Rs {cost_lakhs:.2f}L/month)"
        )
    if overall == "approved":
        return (
            f"APPROVED: {n_sites} site request at Rs {cost_lakhs:.2f}L/month "
            f"- proceeds automatically"
        )
    return (
        f"APPROVED WITH ESCALATION: {n_sites} site request "
        f"at Rs {cost_lakhs:.2f}L/month - needs {approval.upper()} approval"
    )


def evaluate_node(state: PolicyState) -> PolicyState:
    intake = state["intake"]
    checks = [chk(intake) for chk in ALL_CHECKS]

    blocking = [c.details for c in checks if c.status == "fail"]
    total_cost = estimate_total_cost(intake)

    if blocking:
        overall = "rejected"
        approval = "auto"
    elif any(c.status == "warn" for c in checks):
        overall = "approved_with_escalation"
        approval = decide_approval_level(checks, total_cost)
    else:
        overall = "approved"
        approval = "auto"

    summary = _summary_line(
        overall, approval, total_cost / 1_00_000, len(intake.sites)
    )

    result = PolicyResult(
        overall_status=overall,
        approval_level_required=approval,
        checks=checks,
        estimated_cost_inr_monthly=total_cost,
        blocking_violations=blocking,
        summary=summary,
    )
    return {"intake": intake, "result": result}


def build_policy_graph():
    graph = StateGraph(PolicyState)
    graph.add_node("evaluate", evaluate_node)
    graph.set_entry_point("evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile()


def run_policy(intake: IntakeResult) -> PolicyResult:
    app = build_policy_graph()
    final = app.invoke({"intake": intake, "result": None})
    return final["result"]
