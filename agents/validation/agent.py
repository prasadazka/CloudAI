"""
Validation Agent - runs E2E tests after deployment.
Per agents.md §7.

Modes:
  - real     : tests via SSM (requires real apply + EC2 instances)
  - simulated: plausible numbers based on architecture choice (default for plan_only)
  - skipped  : no deployment available
"""

from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.common.schemas import (
    ArchitectureResult,
    DeploymentResult,
    IntakeResult,
    SiteValidation,
    ValidationResult,
)
from agents.validation.simulator import (
    SLA_LATENCY_TARGETS,
    simulate_site_tests,
)


class ValidationState(TypedDict):
    intake: IntakeResult
    architecture: Optional[ArchitectureResult]
    deployment: Optional[DeploymentResult]
    result: Optional[ValidationResult]


def _summarize(sites: list[SiteValidation]) -> tuple[int, int, int, str]:
    passed = sum(1 for s in sites if s.overall == "pass")
    borderline = sum(1 for s in sites if s.overall == "borderline")
    failed = sum(1 for s in sites if s.overall == "fail")

    if failed == 0 and borderline == 0:
        status = "all_pass"
    elif failed == 0:
        status = "pass_with_warnings"
    elif passed > 0:
        status = "some_failed"
    else:
        status = "all_failed"

    return passed, borderline, failed, status


def validate_node(state: ValidationState) -> ValidationState:
    intake = state["intake"]
    architecture = state.get("architecture")
    deployment = state.get("deployment")

    sla_target_uptime_pct = (
        next((o.sla_uptime_pct for o in architecture.options if o.recommended), 99.5)
        if architecture else 99.5
    )

    # Pick mode
    if not architecture:
        state["result"] = ValidationResult(
            status="tests_skipped",
            mode="skipped",
            sla_target_uptime_pct=sla_target_uptime_pct,
            summary="No architecture decision available; validation cannot proceed.",
        )
        return state

    deployment_applied = (
        deployment is not None
        and deployment.status in ("applied", "applied_with_warnings")
    )

    # We have a recommendation but no live infrastructure - simulate
    recommended = next(o for o in architecture.options if o.recommended)

    if deployment_applied:
        # TODO: implement real SSM-driven testing
        # For now, mark as simulated with note that real-mode is roadmap
        mode = "simulated"
        disclaimer = (
            "Live infrastructure detected. Real SSM-driven tests are on the "
            "roadmap; reporting simulated results for now."
        )
    else:
        mode = "simulated"
        disclaimer = (
            "No deployment applied (plan_only or skipped). Results below are "
            "SIMULATED based on the recommended architecture's expected "
            "performance envelope. Real tests will run after terraform apply."
        )

    sites = simulate_site_tests(intake, recommended, seed=42)
    passed, borderline, failed, status = _summarize(sites)
    sla_target_ms = SLA_LATENCY_TARGETS.get(intake.compliance_tier, 50)

    summary = (
        f"{passed}/{len(sites)} sites PASS, "
        f"{borderline} borderline, {failed} failed "
        f"(latency SLA <={sla_target_ms}ms, throughput >=90% of provisioned)"
    )

    state["result"] = ValidationResult(
        status=status,
        mode=mode,
        sla_target_uptime_pct=sla_target_uptime_pct,
        sites_tested=len(sites),
        sites_passed=passed,
        sites_borderline=borderline,
        sites_failed=failed,
        sites_detail=sites,
        summary=summary,
        disclaimer=disclaimer,
    )
    return state


def build_validation_graph():
    graph = StateGraph(ValidationState)
    graph.add_node("validate", validate_node)
    graph.set_entry_point("validate")
    graph.add_edge("validate", END)
    return graph.compile()


def run_validation(
    intake: IntakeResult,
    architecture: Optional[ArchitectureResult] = None,
    deployment: Optional[DeploymentResult] = None,
) -> ValidationResult:
    app = build_validation_graph()
    final = app.invoke({
        "intake": intake,
        "architecture": architecture,
        "deployment": deployment,
        "result": None,
    })
    return final["result"]
