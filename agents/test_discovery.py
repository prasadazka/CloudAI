"""
Test Discovery Agent standalone + via supervisor.
Run from agents/:
    python test_discovery.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.discovery.agent import run_discovery
from agents.intake.agent import run_intake
from agents.supervisor.agent import run_workflow


SCENARIOS = [
    {
        "name": "Existing Gold customer with reusable VPC + TGW",
        "customer": "Bharat Manufacturing Ltd",
        "request": (
            "Onboard 10 retail stores: 5 in Maharashtra and 5 in Karnataka, "
            "100 Mbps SD-WAN, BFSI tier."
        ),
    },
    {
        "name": "New SMB - no reuse possible",
        "customer": "TechStart Pvt Ltd",
        "request": "Onboard 2 office sites in Pune and Mumbai with 50 Mbps SD-WAN each.",
    },
    {
        "name": "Existing customer with near-full TGW",
        "customer": "Rapid Retail India",
        "request": (
            "Onboard 8 new stores in Bangalore, Mysore, Hubli, Chennai, Coimbatore, "
            "Madurai, Salem, Trichy. 100 Mbps SD-WAN."
        ),
    },
    {
        "name": "Brand-new customer never seen before",
        "customer": "Acme Logistics Pvt Ltd",
        "request": "Onboard 3 sites in Pune, Nashik, and Mumbai. Standard tier.",
    },
]


def main():
    print("=" * 75)
    print("DISCOVERY AGENT - 4 SCENARIOS")
    print("=" * 75)

    for i, sc in enumerate(SCENARIOS, 1):
        print(f"\n{'=' * 75}")
        print(f"SCENARIO {i}: {sc['name']}")
        print(f"Customer: {sc['customer']}")
        print(f"{'=' * 75}")

        intake = run_intake(sc["request"])
        result = run_discovery(intake, sc["customer"])

        print(f"\nCustomer Found  : {result.customer_found}")
        if result.customer_profile:
            p = result.customer_profile
            print(f"Profile         : {p.id} ({p.tier}, since {p.since})")
            print(f"Industry        : {p.industry}")
            print(f"Total ARR       : Rs {p.total_arr_inr:,}")
        print(f"Active VPNs     : {result.active_vpn_count}")
        print(f"Recent Incidents: {result.recent_incidents_90d} (90d)")
        print(f"\nExisting Resources ({len(result.existing_resources)}):")
        for r in result.existing_resources:
            print(f"  [{r.type}] {r.id} ({r.region}) {r.cidr or ''} - {r.notes}")
        print(f"\nRecommendations ({len(result.recommendations)}):")
        for rec in result.recommendations:
            print(f"  [{rec.type.upper()}] {rec.resource_id}")
            print(f"     savings: Rs {rec.estimated_savings_inr_monthly:,}/month")
            print(f"     reason : {rec.reasoning}")
        print(
            f"\nTotal Savings   : "
            f"Rs {result.total_estimated_savings_inr_monthly:,}/month"
        )
        print(f"Summary         : {result.summary}")

    print("\n\n" + "=" * 75)
    print("FULL SUPERVISOR FLOW (Intake -> Discovery -> Policy -> Audit)")
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
