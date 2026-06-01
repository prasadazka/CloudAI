"""
Quick test for the Intake Agent.
Run from agents/ folder:
    python test_intake.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.intake.agent import run_intake

TEST_CASES = [
    {
        "name": "Hero Vi demo request",
        "input": (
            "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
            "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
            "Belgaum, Davangere). Each 100 Mbps SD-WAN to AWS Mumbai, priority for "
            "SAP and CCTV, BFSI tier, by month-end."
        ),
    },
    {
        "name": "Vague request (should trigger clarification)",
        "input": "We want to add some sites in south India.",
    },
    {
        "name": "BFSI bank request",
        "input": (
            "Bank branch onboarding: Bangalore + Chennai, MPLS not SD-WAN, "
            "200 Mbps each, RBI compliance required, voice + core banking priority, "
            "deadline July 15."
        ),
    },
]


def main():
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {case['name']}")
        print(f"{'='*70}")
        print(f"INPUT:\n{case['input']}\n")

        try:
            result = run_intake(case["input"])
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        print(f"OUTPUT:")
        print(json.dumps(result.model_dump(), indent=2))

        print(f"\nKEY SIGNALS:")
        print(f"  Intent       : {result.intent}")
        print(f"  Confidence   : {result.confidence}")
        print(f"  Sites found  : {result.site_count}")
        print(f"  Compliance   : {result.compliance_tier}")
        print(f"  Deadline     : {result.deadline}")
        if result.needs_clarification:
            print(f"  CLARIFY      : {result.clarification_question}")


if __name__ == "__main__":
    main()
