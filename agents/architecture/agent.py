"""
Architecture Agent - designs 2-3 solution options with tradeoffs.

Per agents.md §4:
  - Always generate 2-3 options (never just one)
  - Cost + resilience + complexity tradeoffs
  - Reuse Discovery findings (apply savings to all options)
  - Recommend option matching customer tier
"""

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import (
    ArchitectureOption,
    ArchitectureResult,
    DiscoveryResult,
    IntakeResult,
)
from agents.policy.rules import estimate_total_cost


# Architecture multipliers vs baseline (dual-VPN BGP = 1.0x = matches policy)
COST_MULTIPLIERS = {
    "hub_spoke_single_vpn": 0.65,
    "hub_spoke_dual_vpn": 0.85,
    "hub_spoke_dual_vpn_bgp": 1.0,
    "full_mesh_dual_vpn": 1.40,
}


def _build_options(
    intake: IntakeResult, discovery: Optional[DiscoveryResult]
) -> list[ArchitectureOption]:
    base = estimate_total_cost(intake)
    savings = (
        discovery.total_estimated_savings_inr_monthly
        if discovery and discovery.customer_found
        else 0
    )
    net_base = max(base - savings, 0)

    opts: list[ArchitectureOption] = [
        ArchitectureOption(
            name="Option A: Cost-Optimized",
            topology="hub_spoke_single_vpn",
            cost_inr_monthly=int(net_base * COST_MULTIPLIERS["hub_spoke_single_vpn"]),
            resilience_score=6.5,
            complexity="low",
            sla_uptime_pct=99.5,
            tradeoffs=(
                "Single VPN per site. 30-60 min recovery on tunnel failure. "
                "Suitable for non-critical workloads."
            ),
            reasoning="Lowest cost; acceptable for SMB / non-regulated workloads.",
        ),
        ArchitectureOption(
            name="Option B: Resilient (Dual-VPN BGP)",
            topology="hub_spoke_dual_vpn_bgp",
            cost_inr_monthly=int(net_base * COST_MULTIPLIERS["hub_spoke_dual_vpn_bgp"]),
            resilience_score=9.2,
            complexity="medium",
            sla_uptime_pct=99.99,
            tradeoffs=(
                "Dual VPN tunnels with BGP-based sub-second failover. "
                "Meets BFSI / regulated workload SLAs."
            ),
            reasoning=(
                "Best balance of cost vs reliability for enterprise / BFSI customers."
            ),
        ),
        ArchitectureOption(
            name="Option C: Premium (Full-Mesh)",
            topology="full_mesh_dual_vpn",
            cost_inr_monthly=int(net_base * COST_MULTIPLIERS["full_mesh_dual_vpn"]),
            resilience_score=9.8,
            complexity="high",
            sla_uptime_pct=99.999,
            tradeoffs=(
                "Full mesh dual-VPN. Highest resilience but ~40% costlier. "
                "Recommended only for >50 sites or multi-region critical workloads."
            ),
            reasoning="Over-engineered for typical site counts; reserve for hyperscale.",
        ),
    ]
    return opts


def _pick_recommendation(
    intake: IntakeResult, opts: list[ArchitectureOption]
) -> tuple[str, str]:
    """Returns (recommended_option_name, rationale)."""
    n_sites = intake.site_count
    tier = intake.compliance_tier

    if tier in ("BFSI_equivalent", "Government", "Healthcare"):
        return (
            opts[1].name,  # Option B
            (
                f"{tier} compliance tier requires 99.99% SLA. "
                f"Option A (99.5%) does not meet this. "
                f"Option C overshoots at higher cost without proportional benefit. "
                f"Option B is the right fit."
            ),
        )

    if n_sites >= 50:
        return (
            opts[2].name,  # Option C
            (
                f"{n_sites} sites benefit from full-mesh topology - "
                f"reduces hub bottleneck and provides best resilience at scale."
            ),
        )

    return (
        opts[0].name,  # Option A
        (
            f"Standard tier with {n_sites} sites. "
            f"Option A provides best cost / value. "
            f"Upgrade to Option B if uptime SLA tightens later."
        ),
    )


def design_node(state: dict) -> dict:
    intake: IntakeResult = state["intake"]
    discovery: Optional[DiscoveryResult] = state.get("discovery")

    options = _build_options(intake, discovery)
    recommended_name, rationale = _pick_recommendation(intake, options)
    for opt in options:
        opt.recommended = opt.name == recommended_name

    chosen = next(o for o in options if o.recommended)
    summary = (
        f"Recommended {chosen.name} - "
        f"Rs {chosen.cost_inr_monthly/1_00_000:.2f}L/month, "
        f"{chosen.sla_uptime_pct}% SLA, resilience {chosen.resilience_score}/10"
    )

    state["result"] = ArchitectureResult(
        options=options,
        recommended_option_name=recommended_name,
        rationale=rationale,
        summary=summary,
    )
    return state


class ArchitectureState(TypedDict):
    intake: IntakeResult
    discovery: Optional[DiscoveryResult]
    result: Optional[ArchitectureResult]


def build_architecture_graph():
    graph = StateGraph(ArchitectureState)
    graph.add_node("design", design_node)
    graph.set_entry_point("design")
    graph.add_edge("design", END)
    return graph.compile()


def run_architecture(
    intake: IntakeResult,
    discovery: Optional[DiscoveryResult] = None,
) -> ArchitectureResult:
    app = build_architecture_graph()
    final = app.invoke({
        "intake": intake,
        "discovery": discovery,
        "result": None,
    })
    return final["result"]
