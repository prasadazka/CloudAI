"""
Mock Vi BSS customer database.
In production this would query Netcracker/Amdocs OSS/BSS via TM Forum APIs.
For demo: prebuilt profiles + realistic existing infrastructure.
"""

from agents.common.schemas import (
    CustomerProfile,
    ExistingResource,
    ReuseRecommendation,
)


# Each customer entry: profile + existing infra + active VPNs + recent incidents
CUSTOMERS = {
    "bharat manufacturing ltd": {
        "profile": CustomerProfile(
            id="VICUST-2042",
            name="Bharat Manufacturing Ltd",
            tier="Enterprise_Gold",
            since="2022-04-15",
            total_arr_inr=4500000,
            industry="Manufacturing",
            primary_contact="amol.deshmukh@bharatmfg.in",
        ),
        "resources": [
            ExistingResource(
                type="vpc",
                id="vpc-abc12345",
                region="ap-south-1",
                cidr="10.0.0.0/16",
                notes="Primary AWS Mumbai VPC, SAP HANA workload, ample headroom",
            ),
            ExistingResource(
                type="transit_gateway",
                id="tgw-9f8e7d6c",
                region="ap-south-1",
                notes="Customer HQ TGW with 12/50 attachments used",
            ),
        ],
        "active_vpns": 20,
        "recent_incidents_90d": 1,
    },
    "techstart pvt ltd": {
        "profile": CustomerProfile(
            id="VICUST-9981",
            name="TechStart Pvt Ltd",
            tier="SMB",
            since="2025-11-02",
            total_arr_inr=620000,
            industry="Technology",
            primary_contact="ops@techstart.in",
        ),
        "resources": [],
        "active_vpns": 0,
        "recent_incidents_90d": 0,
    },
    "adventure resorts pvt ltd": {
        "profile": CustomerProfile(
            id="VICUST-7711",
            name="Adventure Resorts Pvt Ltd",
            tier="Enterprise_Silver",
            since="2024-08-19",
            total_arr_inr=1850000,
            industry="Hospitality",
            primary_contact="cio@advresorts.in",
        ),
        "resources": [
            ExistingResource(
                type="vpc",
                id="vpc-resort01",
                region="ap-south-1",
                cidr="172.16.0.0/16",
                notes="Booking engine + CRM workloads",
            ),
        ],
        "active_vpns": 4,
        "recent_incidents_90d": 2,
    },
    "rapid retail india": {
        "profile": CustomerProfile(
            id="VICUST-3344",
            name="Rapid Retail India",
            tier="Enterprise_Gold",
            since="2021-02-10",
            total_arr_inr=8200000,
            industry="Retail",
            primary_contact="dharani@rapidretail.in",
        ),
        "resources": [
            ExistingResource(
                type="vpc",
                id="vpc-retail-prod",
                region="ap-south-1",
                cidr="10.20.0.0/16",
                notes="POS + inventory + analytics workloads",
            ),
            ExistingResource(
                type="transit_gateway",
                id="tgw-rretail-01",
                region="ap-south-1",
                notes="Retail TGW with 40/50 attachments used",
            ),
        ],
        "active_vpns": 38,
        "recent_incidents_90d": 0,
    },
}


# Per-VPC reuse savings (avoids creating new VPC, NAT, IGW per site batch)
SAVINGS_PER_REUSED_VPC_INR = 40_000
# Per-TGW reuse savings (avoids new TGW + attachment fees)
SAVINGS_PER_REUSED_TGW_INR = 28_000
# Threshold: if TGW already has near-capacity attachments, recommend new TGW
TGW_CAPACITY_WARN = 45


def lookup_customer(name: str) -> dict | None:
    """Case-insensitive customer lookup. Returns None if not found."""
    return CUSTOMERS.get(name.strip().lower())


def compute_recommendations(
    customer_data: dict, requested_site_count: int
) -> tuple[list[ReuseRecommendation], int]:
    """Returns recommendations + total estimated savings INR/month."""
    recs: list[ReuseRecommendation] = []
    savings_total = 0

    for r in customer_data["resources"]:
        if r.type == "vpc":
            recs.append(ReuseRecommendation(
                type="reuse",
                resource_id=r.id,
                estimated_savings_inr_monthly=SAVINGS_PER_REUSED_VPC_INR,
                reasoning=(
                    f"Reuse existing VPC {r.id} ({r.cidr}) for central hub. "
                    f"Avoids duplicate VPC + NAT charges."
                ),
            ))
            savings_total += SAVINGS_PER_REUSED_VPC_INR

        elif r.type == "transit_gateway":
            # Crude capacity heuristic from notes (looks for "X/Y attachments used")
            capacity_ok = True
            note_lower = r.notes.lower()
            if "/50 attachments used" in note_lower:
                try:
                    used = int(
                        note_lower.split("/50")[0].rsplit(" ", 1)[-1]
                    )
                    if used + requested_site_count > TGW_CAPACITY_WARN:
                        capacity_ok = False
                except (ValueError, IndexError):
                    pass

            if capacity_ok:
                recs.append(ReuseRecommendation(
                    type="reuse",
                    resource_id=r.id,
                    estimated_savings_inr_monthly=SAVINGS_PER_REUSED_TGW_INR,
                    reasoning=(
                        f"Reuse existing Transit Gateway {r.id}. "
                        f"Capacity headroom sufficient for {requested_site_count} new sites."
                    ),
                ))
                savings_total += SAVINGS_PER_REUSED_TGW_INR
            else:
                recs.append(ReuseRecommendation(
                    type="skip_create",
                    resource_id=r.id,
                    estimated_savings_inr_monthly=0,
                    reasoning=(
                        f"Existing TGW {r.id} near capacity. "
                        f"Recommend creating a second TGW for this batch."
                    ),
                ))

    return recs, savings_total
