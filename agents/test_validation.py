"""
Test Validation Agent (simulated mode, since plan_only has no live infra).
Run from agents/:
    python test_validation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.supervisor.agent import run_workflow


HERO_REQUEST = (
    "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
    "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
    "Belgaum, Davangere). 100 Mbps SD-WAN, BFSI tier."
)


def main():
    print("=" * 75)
    print("FULL 8-AGENT PIPELINE")
    print("=" * 75)

    state = run_workflow(
        HERO_REQUEST,
        customer_name="Bharat Manufacturing Ltd",
        deployment_mode="plan_only",
    )

    if state.get("validation"):
        v = state["validation"]
        print(f"\nValidation status : {v.status}")
        print(f"Mode              : {v.mode}")
        print(f"SLA target uptime : {v.sla_target_uptime_pct}%")
        print(f"Summary           : {v.summary}")
        if v.disclaimer:
            print(f"\nDISCLAIMER: {v.disclaimer}")
        print(f"\nPer-site results ({v.sites_tested}):")
        print(f"  Passed     : {v.sites_passed}")
        print(f"  Borderline : {v.sites_borderline}")
        print(f"  Failed     : {v.sites_failed}")
        for sv in v.sites_detail[:3]:
            print(f"\n  Site: {sv.site_name} - overall {sv.overall.upper()}")
            for t in sv.tests:
                icon = {"pass": "[OK]", "fail": "[X]", "borderline": "[!]", "skipped": "[-]"}.get(t.outcome, "?")
                print(f"    {icon} {t.name}: {t.measured} (target {t.target})")
        if v.sites_tested > 3:
            print(f"  ... and {v.sites_tested - 3} more sites")

    if state.get("audit_pdf_path"):
        print(f"\nAudit PDF: {state['audit_pdf_path']}")

    print("\nAGENT TRACE:")
    for line in state["trace"]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
