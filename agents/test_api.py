"""
Live API test - runs the full hero scenario against a running FastAPI.
Start the API first in another terminal:
    python run_api.py

Then run this:
    python test_api.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import urllib.request
import urllib.error
import json


BASE = "http://127.0.0.1:8000"

HERO_REQUEST = (
    "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, "
    "Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, "
    "Belgaum, Davangere). 100 Mbps SD-WAN, BFSI tier."
)


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main():
    print("=" * 70)
    print("STEP 1: Health check")
    print("=" * 70)
    try:
        health = _get(f"{BASE}/health")
        print(json.dumps(health, indent=2))
    except urllib.error.URLError as e:
        print(f"ERROR: API not reachable at {BASE}")
        print(f"Reason: {e}")
        print("\nStart the API first:  python run_api.py")
        return

    print("\n" + "=" * 70)
    print("STEP 2: Create workflow (POST /workflows)")
    print("=" * 70)
    create = _post(f"{BASE}/workflows", {
        "user_request": HERO_REQUEST,
        "customer_name": "Bharat Manufacturing Ltd",
        "deployment_mode": "plan_only",
    })
    print(json.dumps(create, indent=2))
    wf_id = create["workflow_id"]

    print("\n" + "=" * 70)
    print(f"STEP 3: Poll trace until done ({BASE}/workflows/{wf_id}/trace)")
    print("=" * 70)
    last_count = 0
    for i in range(120):  # max 2 min
        time.sleep(1)
        trace = _get(f"{BASE}/workflows/{wf_id}/trace")
        new_lines = trace["trace"][last_count:]
        for line in new_lines:
            print(f"  {line}")
        last_count = len(trace["trace"])
        if trace["finished"]:
            print(f"\n  >>> finished after ~{i+1}s, status={trace['status']}")
            break

    print("\n" + "=" * 70)
    print(f"STEP 4: Get summary (GET /workflows/{wf_id})")
    print("=" * 70)
    summary = _get(f"{BASE}/workflows/{wf_id}")
    print(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 70)
    print(f"STEP 5: Download PDF (GET /workflows/{wf_id}/pdf)")
    print("=" * 70)
    if summary.get("audit_pdf_available"):
        pdf_url = f"{BASE}/workflows/{wf_id}/pdf"
        local = Path(f"api_test_{wf_id}.pdf")
        with urllib.request.urlopen(pdf_url, timeout=15) as r:
            local.write_bytes(r.read())
        print(f"  PDF saved to: {local.resolve()}  ({local.stat().st_size:,} bytes)")
    else:
        print("  PDF not yet available")

    print("\n" + "=" * 70)
    print("STEP 6: List recent workflows (GET /workflows)")
    print("=" * 70)
    listed = _get(f"{BASE}/workflows?limit=5")
    for w in listed:
        print(
            f"  {w['workflow_id']} | {w['customer_name']:<28} | "
            f"{w['status']:<10} | sites={w['site_count']} | "
            f"decision={w.get('final_decision') or '-'}"
        )

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
