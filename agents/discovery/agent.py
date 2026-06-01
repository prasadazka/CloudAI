"""
Discovery Agent - looks up existing customer infrastructure and recommends reuse.

Tools (per agents.md §2):
  - get_customer_profile(customer_name)
  - list_existing_resources(customer_data)
  - calculate_reuse_savings(customer_data, requested_site_count)

In production these would query Vi BSS (Netcracker/Amdocs via TM Forum APIs)
and AWS describe-* operations. Demo uses mocked store in customers.py.
"""

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import (
    CustomerProfile,
    DiscoveryResult,
    IntakeResult,
)
from agents.discovery.customers import compute_recommendations, lookup_customer


class DiscoveryState(TypedDict):
    intake: IntakeResult
    customer_name: str
    result: Optional[DiscoveryResult]


def discover_node(state: DiscoveryState) -> DiscoveryState:
    intake = state["intake"]
    name = state["customer_name"]

    data = lookup_customer(name)

    if data is None:
        result = DiscoveryResult(
            customer_found=False,
            customer_profile=CustomerProfile(
                id=f"NEW-{abs(hash(name)) % 10000:04d}",
                name=name,
                tier="New",
                since="-",
                industry="Unknown",
            ),
            existing_resources=[],
            active_vpn_count=0,
            recommendations=[],
            recent_incidents_90d=0,
            total_estimated_savings_inr_monthly=0,
            summary=(
                f"New customer '{name}' - greenfield deployment, "
                f"no reuse opportunities. Standard onboarding flow."
            ),
        )
        return {"intake": intake, "customer_name": name, "result": result}

    recs, savings = compute_recommendations(data, max(intake.site_count, 1))

    if savings > 0:
        summary = (
            f"Existing {data['profile'].tier} customer "
            f"({data['active_vpns']} active VPNs). "
            f"{len(recs)} reuse opportunity(ies) identified - "
            f"estimated Rs {savings/1_00_000:.2f}L/month savings."
        )
    else:
        summary = (
            f"Existing {data['profile'].tier} customer "
            f"({data['active_vpns']} active VPNs). "
            f"No direct reuse opportunities for this request."
        )

    result = DiscoveryResult(
        customer_found=True,
        customer_profile=data["profile"],
        existing_resources=data["resources"],
        active_vpn_count=data["active_vpns"],
        recommendations=recs,
        recent_incidents_90d=data["recent_incidents_90d"],
        total_estimated_savings_inr_monthly=savings,
        summary=summary,
    )
    return {"intake": intake, "customer_name": name, "result": result}


def build_discovery_graph():
    graph = StateGraph(DiscoveryState)
    graph.add_node("discover", discover_node)
    graph.set_entry_point("discover")
    graph.add_edge("discover", END)
    return graph.compile()


def run_discovery(
    intake: IntakeResult, customer_name: str
) -> DiscoveryResult:
    app = build_discovery_graph()
    final = app.invoke({
        "intake": intake,
        "customer_name": customer_name,
        "result": None,
    })
    return final["result"]
