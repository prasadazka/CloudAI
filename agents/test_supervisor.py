"""
Test the Supervisor Agent end-to-end.
Demonstrates all 4 routing paths:
  1. Clear request -> Intake -> Policy -> Audit (approved)
  2. Vague request -> Intake (clarification)
  3. Out-of-coverage -> Intake -> Policy (rejected) -> Audit
  4. Small standard -> Intake -> Policy (auto) -> Audit
Run from agents/ folder:
    python test_supervisor.py
"""

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.supervisor.agent import run_workflow


SCENARIOS = [
    {
        "name": "Hero Vi demo - 10 BFSI sites",
        "customer": "Bharat Manufacturing Ltd",
        "input": (
            "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
            "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
            "Belgaum, Davangere). Each 100 Mbps SD-WAN to AWS Mumbai, priority "
            "for SAP and CCTV, BFSI tier, by month-end."
        ),
    },
    {
        "name": "Vague request - should trigger clarification",
        "customer": "Unknown Customer",
        "input": "We want to add some sites in south India.",
    },
    {
        "name": "Out-of-coverage - should be rejected",
        "customer": "Adventure Resorts Pvt Ltd",
        "input": "Onboard 3 sites in Leh, Srinagar, and Port Blair with 100 Mbps SD-WAN.",
    },
    {
        "name": "Small standard - should auto-approve",
        "customer": "TechStart Pvt Ltd",
        "input": "Onboard 2 office sites in Pune and Mumbai with 50 Mbps SD-WAN each, standard tier.",
    },
]


def main():
    # Clean old PDFs
    audits_dir = Path("audits")
    if audits_dir.exists():
        for f in audits_dir.glob("*.pdf"):
            f.unlink()

    for i, sc in enumerate(SCENARIOS, 1):
        print("\n" + "=" * 75)
        print(f"SCENARIO {i}: {sc['name']}")
        print(f"Customer: {sc['customer']}")
        print("=" * 75)
        print(f"INPUT: {sc['input']}\n")

        try:
            state = run_workflow(sc["input"], customer_name=sc["customer"])
        except Exception as e:
            print(f"WORKFLOW ERROR: {type(e).__name__}: {e}")
            continue

        print(f"DECISION : {state['final_decision'].upper()}")
        if state.get("clarification_question"):
            print(f"QUESTION : {state['clarification_question']}")
        if state.get("policy"):
            pol = state["policy"]
            print(f"COST     : Rs {pol.estimated_cost_inr_monthly/1_00_000:.2f}L/month")
            print(f"APPROVAL : {pol.approval_level_required.upper()}")
        if state.get("audit_pdf_path"):
            print(f"PDF      : {state['audit_pdf_path']}")
        if state.get("error"):
            print(f"ERROR    : {state['error']}")

        print(f"\nAGENT TRACE ({len(state['trace'])} events):")
        for line in state["trace"]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
