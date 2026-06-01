"""
Test IaC Agent standalone + full supervisor flow.
Run from repo root or agents/:
    python agents/test_iac.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.architecture.agent import run_architecture
from agents.discovery.agent import run_discovery
from agents.iac.agent import run_iac
from agents.intake.agent import run_intake
from agents.supervisor.agent import run_workflow


HERO_REQUEST = (
    "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
    "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
    "Belgaum, Davangere). 100 Mbps SD-WAN, BFSI tier, by month-end."
)


def main():
    print("=" * 75)
    print("IaC AGENT - STANDALONE")
    print("=" * 75)

    intake = run_intake(HERO_REQUEST)
    discovery = run_discovery(intake, "Bharat Manufacturing Ltd")
    architecture = run_architecture(intake, discovery)

    workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    result = run_iac(
        workflow_id=workflow_id,
        customer_name="Bharat Manufacturing Ltd",
        intake=intake,
        discovery=discovery,
        architecture=architecture,
    )

    print(f"\nStatus           : {result.status}")
    print(f"Workflow dir     : {result.workflow_dir}")
    print(f"Files generated  : {len(result.artifacts)}")
    for a in result.artifacts:
        print(f"  - {a.path} ({a.line_count} lines)")
    print(f"Resources planned: {result.resources_planned}")
    print(f"Self-fix attempts: {result.self_fix_attempts}")
    print(f"Diff summary     : {result.diff_summary}")
    print(f"\nValidation output:\n{result.validation_output}")

    print("\n\n" + "=" * 75)
    print("FULL SUPERVISOR FLOW (6 agents)")
    print("=" * 75)
    state = run_workflow(HERO_REQUEST, customer_name="Bharat Manufacturing Ltd")
    print(f"\nFinal decision: {state['final_decision']}")
    if state.get("iac"):
        print(f"IaC workflow dir: {state['iac'].workflow_dir}")
    if state.get("audit_pdf_path"):
        print(f"Audit PDF       : {state['audit_pdf_path']}")
    print("\nAGENT TRACE:")
    for line in state["trace"]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
