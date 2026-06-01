"""
Quick test for the Policy Agent.
Pipes Intake Agent output -> Policy Agent.
Run from agents/ folder:
    python test_policy.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.intake.agent import run_intake
from agents.policy.agent import run_policy

TEST_CASES = [
    {
        "name": "Hero Vi demo request (10 sites BFSI)",
        "input": (
            "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
            "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
            "Belgaum, Davangere). Each 100 Mbps SD-WAN to AWS Mumbai, priority for "
            "SAP and CCTV, BFSI tier, by month-end."
        ),
    },
    {
        "name": "Small standard request (should auto-approve)",
        "input": (
            "Onboard 2 office sites in Pune and Mumbai with 50 Mbps SD-WAN each, "
            "no special compliance, standard SLA."
        ),
    },
    {
        "name": "Out-of-coverage request (should fail DOT licensing)",
        "input": (
            "Onboard 3 sites in Leh, Srinagar, and Port Blair with 100 Mbps SD-WAN."
        ),
    },
]


def print_policy_result(result):
    print(f"\nOVERALL: {result.overall_status.upper()}")
    print(f"APPROVAL LEVEL: {result.approval_level_required.upper()}")
    print(f"ESTIMATED COST: Rs {result.estimated_cost_inr_monthly/1_00_000:.2f}L/month")
    print(f"SUMMARY: {result.summary}")
    print(f"\nCHECKS:")
    for c in result.checks:
        icon = {"pass": "[OK]", "warn": "[!]", "fail": "[X]"}.get(c.status, "?")
        print(f"  {icon} {c.name}: {c.details}")
        if c.action_required:
            print(f"      ACTION: {c.action_required}")


def main():
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {case['name']}")
        print(f"{'='*70}")
        print(f"INPUT:\n{case['input']}\n")

        try:
            intake = run_intake(case["input"])
            print(f"Intake confidence: {intake.confidence}")
            print(f"Intake sites    : {intake.site_count}")

            policy = run_policy(intake)
            print_policy_result(policy)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
