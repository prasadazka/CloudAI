"""
Test Architecture Agent standalone + full supervisor flow.
Run from agents/:
    python test_architecture.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.architecture.agent import run_architecture
from agents.discovery.agent import run_discovery
from agents.intake.agent import run_intake
from agents.supervisor.agent import run_workflow


SCENARIOS = [
    {
        "name": "BFSI request - should recommend Option B (resilient)",
        "customer": "Bharat Manufacturing Ltd",
        "request": (
            "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
            "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
            "Belgaum, Davangere). 100 Mbps SD-WAN, BFSI tier."
        ),
    },
    {
        "name": "Standard SMB request - should recommend Option A (cheapest)",
        "customer": "TechStart Pvt Ltd",
        "request": (
            "Onboard 2 office sites in Pune and Mumbai with 50 Mbps SD-WAN each, "
            "standard tier."
        ),
    },
]


def print_options(arch):
    for opt in arch.options:
        mark = " <-- RECOMMENDED" if opt.recommended else ""
        print(f"\n  {opt.name}{mark}")
        print(f"    topology   : {opt.topology}")
        print(f"    cost       : Rs {opt.cost_inr_monthly/1_00_000:.2f}L/month")
        print(f"    resilience : {opt.resilience_score}/10")
        print(f"    complexity : {opt.complexity}")
        print(f"    SLA uptime : {opt.sla_uptime_pct}%")
        print(f"    tradeoffs  : {opt.tradeoffs}")
    print(f"\nRATIONALE: {arch.rationale}")
    print(f"SUMMARY  : {arch.summary}")


def main():
    print("=" * 75)
    print("ARCHITECTURE AGENT - STANDALONE")
    print("=" * 75)

    for i, sc in enumerate(SCENARIOS, 1):
        print(f"\n{'=' * 75}")
        print(f"SCENARIO {i}: {sc['name']}")
        print(f"Customer: {sc['customer']}")
        print(f"{'=' * 75}")

        intake = run_intake(sc["request"])
        discovery = run_discovery(intake, sc["customer"])
        arch = run_architecture(intake, discovery)
        print_options(arch)

    print("\n\n" + "=" * 75)
    print("FULL SUPERVISOR FLOW (5 agents: Intake -> Discovery -> Policy -> Architecture -> Audit)")
    print("=" * 75)
    state = run_workflow(
        SCENARIOS[0]["request"],
        customer_name=SCENARIOS[0]["customer"],
    )
    print(f"\nFinal decision: {state['final_decision']}")
    print(f"PDF: {state.get('audit_pdf_path')}")
    print("\nAGENT TRACE:")
    for line in state["trace"]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
