"""
Test Deployment Agent (plan_only mode by default - no AWS cost).
Run from agents/:
    python test_deployment.py
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
    print("FULL 7-AGENT PIPELINE - DEPLOYMENT IN plan_only MODE (no AWS cost)")
    print("=" * 75)

    state = run_workflow(
        HERO_REQUEST,
        customer_name="Bharat Manufacturing Ltd",
        deployment_mode="plan_only",
    )

    print(f"\nFinal decision : {state['final_decision']}")
    if state.get("deployment"):
        d = state["deployment"]
        print(f"Deployment     : {d.status}")
        print(f"  Mode         : {d.mode}")
        print(f"  Duration     : {d.total_duration_sec:.1f}s")
        print(f"  Summary      : {d.summary}")
        print(f"  Sites tracked: {d.sites_total}")
        for s in d.sites_detail[:5]:
            print(f"    - {s.site_name}: {s.status}")
        if d.sites_total > 5:
            print(f"    ... and {d.sites_total - 5} more")
        print(f"\n--- Terraform output tail (last 30 lines) ---")
        print("\n".join(d.terraform_output_tail.splitlines()[-30:]))
    if state.get("audit_pdf_path"):
        print(f"\nAudit PDF: {state['audit_pdf_path']}")

    print("\nAGENT TRACE:")
    for line in state["trace"]:
        print(f"  {line}")

    print("\n" + "=" * 75)
    print("To actually deploy to AWS (will cost ~Rs 13/hr until destroyed):")
    print("=" * 75)
    print("""
    state = run_workflow(
        '...request...',
        customer_name='...',
        deployment_mode='apply',
        approval_token='NOC-APPROVED-V1',
    )
    """)
    print("Remember to destroy afterwards:")
    print("""
    state = run_workflow(
        '...same request...',
        customer_name='...',
        deployment_mode='destroy',
        approval_token='NOC-APPROVED-V1',
    )
    """)


if __name__ == "__main__":
    main()
