"""
End-to-end test: NL request -> Intake -> Policy -> Audit PDF.
Run from agents/ folder:
    python test_audit.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.audit.generator import build_audit
from agents.intake.agent import run_intake
from agents.policy.agent import run_policy

HERO_REQUEST = (
    "Onboard 10 retail stores for Bharat Manufacturing Ltd: "
    "5 in Maharashtra (Pune, Nashik, Aurangabad, Solapur, Kolhapur) and "
    "5 in Karnataka (Mysore, Hubli, Mangalore, Belgaum, Davangere). "
    "Each 100 Mbps SD-WAN to AWS Mumbai, priority for SAP and CCTV, "
    "BFSI tier, by month-end."
)


def main():
    print("=" * 70)
    print("PIPELINE: Intake -> Policy -> Audit PDF")
    print("=" * 70)

    # Clean old PDFs to avoid confusion
    audits_dir = Path("audits")
    if audits_dir.exists():
        for old in audits_dir.glob("*.pdf"):
            old.unlink()
        print(f"\n[cleanup] Removed old PDFs from {audits_dir}/")

    print("\n[1/3] Running Intake Agent...")
    intake = run_intake(HERO_REQUEST)
    print(f"      OK - {intake.site_count} sites, confidence {intake.confidence}")

    print("\n[2/3] Running Policy Agent...")
    policy = run_policy(intake)
    print(f"      OK - {policy.overall_status} (level: {policy.approval_level_required})")
    print(f"      Cost: Rs {policy.estimated_cost_inr_monthly:,}/month")

    print("\n[3/3] Generating Audit PDF...")
    pdf_path = build_audit(
        intake=intake,
        policy=policy,
        customer_name="Bharat Manufacturing Ltd",
        output_dir="audits",
        approval_signoff="PENDING - CISO review",
    )
    print(f"      OK - {pdf_path}")
    print(f"      File size: {os.path.getsize(pdf_path):,} bytes")

    print("\n" + "=" * 70)
    print(f"DONE. Opening the PDF...")
    print(f"   {pdf_path}")
    print("=" * 70)

    # Auto-open on Windows
    try:
        os.startfile(pdf_path)
    except Exception as e:
        print(f"(Auto-open failed: {e} - open manually)")


if __name__ == "__main__":
    main()
