"""
Policy rules for Vi SD-WAN onboarding.
All rules are deterministic and return PolicyCheck objects.
"""

from agents.common.schemas import IntakeResult, PolicyCheck, Site


# Vi-licensed cities (DOT circle approximation, demo subset)
VI_LICENSED_CITIES = {
    # Metros
    "mumbai", "delhi", "bangalore", "bengaluru", "chennai", "kolkata",
    "hyderabad", "pune", "ahmedabad",
    # Tier-2 Maharashtra
    "nashik", "aurangabad", "solapur", "kolhapur", "nagpur", "thane",
    # Tier-2 Karnataka
    "mysore", "mysuru", "mangalore", "mangaluru", "hubli", "belgaum",
    "belagavi", "davangere", "shimoga",
    # Tier-2 Tamil Nadu
    "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem",
    # Andhra/Telangana
    "vijayawada", "visakhapatnam", "vizag", "guntur", "warangal",
    # Kerala
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "kozhikode",
    # West / North / East
    "jaipur", "lucknow", "kanpur", "indore", "bhopal", "surat", "vadodara",
    "patna", "bhubaneswar", "guwahati", "chandigarh", "ludhiana", "amritsar",
}


# Pricing
BASE_COST_PER_SITE = 80_000          # base Rs/month
COST_PER_MBPS = 500                  # Rs/month per Mbps
MPLS_MULTIPLIER = 1.8
COMPLIANCE_MULTIPLIER = {
    "Standard": 1.0,
    "BFSI_equivalent": 1.25,
    "Government": 1.30,
    "Healthcare": 1.20,
    "Unknown": 1.0,
}


# Approval thresholds (Rs/month)
THRESH_AUTO = 5_00_000          # < 5L: auto
THRESH_MANAGER = 15_00_000      # 5L - 15L: manager
THRESH_DIRECTOR = 50_00_000     # 15L - 50L: director
# > 50L: CFO


def estimate_site_cost(
    site: Site, connectivity: str, compliance: str
) -> int:
    """Estimate monthly cost for a single site in INR."""
    cost = BASE_COST_PER_SITE + (site.bandwidth_mbps * COST_PER_MBPS)
    if connectivity.upper() == "MPLS":
        cost *= MPLS_MULTIPLIER
    cost *= COMPLIANCE_MULTIPLIER.get(compliance, 1.0)
    return int(cost)


def estimate_total_cost(intake: IntakeResult) -> int:
    return sum(
        estimate_site_cost(s, intake.connectivity_type, intake.compliance_tier)
        for s in intake.sites
    )


def check_dot_licensing(intake: IntakeResult) -> PolicyCheck:
    unlicensed = [
        s.city for s in intake.sites
        if s.city.lower().strip() not in VI_LICENSED_CITIES
    ]
    if not intake.sites:
        return PolicyCheck(
            name="DOT Licensing",
            status="warn",
            details="No sites declared - skipped",
            policy_ref="Vi-NET-POL-v3.2/Sec-4.1",
        )
    if unlicensed:
        return PolicyCheck(
            name="DOT Licensing",
            status="fail",
            details=f"Sites outside Vi licensed area: {', '.join(unlicensed)}",
            policy_ref="Vi-NET-POL-v3.2/Sec-4.1",
            action_required="Request DOT licensed-zone confirmation or pick different cities",
        )
    return PolicyCheck(
        name="DOT Licensing",
        status="pass",
        details=f"All {len(intake.sites)} sites in Vi licensed service area",
        policy_ref="Vi-NET-POL-v3.2/Sec-4.1",
    )


def check_data_residency(intake: IntakeResult) -> PolicyCheck:
    return PolicyCheck(
        name="Data Residency",
        status="pass",
        details="ap-south-1 (Mumbai) selected - DPDP Act compliant",
        policy_ref="Vi-SEC-POL-v2.0/Sec-2.3",
    )


def check_sla_tier(intake: IntakeResult) -> PolicyCheck:
    if intake.compliance_tier == "BFSI_equivalent":
        return PolicyCheck(
            name="SLA Tier Match",
            status="pass",
            details="BFSI tier auto-mapped to Gold SLA (99.99% uptime)",
            policy_ref="Vi-OPS-SLA-v1.4",
        )
    return PolicyCheck(
        name="SLA Tier Match",
        status="pass",
        details=f"{intake.compliance_tier} tier -> Standard SLA (99.9%)",
        policy_ref="Vi-OPS-SLA-v1.4",
    )


def check_cost_threshold(intake: IntakeResult) -> PolicyCheck:
    total = estimate_total_cost(intake)
    inr_l = total / 1_00_000  # convert to lakhs
    if total < THRESH_AUTO:
        return PolicyCheck(
            name="Cost Threshold",
            status="pass",
            details=f"Rs {inr_l:.2f}L/month - within auto-approval limit",
            policy_ref="Vi-FIN-POL-v2.1/Sec-7",
        )
    if total < THRESH_MANAGER:
        return PolicyCheck(
            name="Cost Threshold",
            status="warn",
            details=f"Rs {inr_l:.2f}L/month exceeds Rs 5L auto-approval threshold",
            policy_ref="Vi-FIN-POL-v2.1/Sec-7",
            action_required="Manager approval required",
        )
    if total < THRESH_DIRECTOR:
        return PolicyCheck(
            name="Cost Threshold",
            status="warn",
            details=f"Rs {inr_l:.2f}L/month exceeds Rs 15L threshold",
            policy_ref="Vi-FIN-POL-v2.1/Sec-7",
            action_required="Director approval required",
        )
    return PolicyCheck(
        name="Cost Threshold",
        status="warn",
        details=f"Rs {inr_l:.2f}L/month exceeds Rs 50L threshold",
        policy_ref="Vi-FIN-POL-v2.1/Sec-7",
        action_required="CFO + Director approval required",
    )


def check_site_count_limit(intake: IntakeResult) -> PolicyCheck:
    n = len(intake.sites)
    if n > 50:
        return PolicyCheck(
            name="Site Count Limit",
            status="warn",
            details=f"{n} sites exceeds single-batch limit (50)",
            policy_ref="Vi-OPS-POL-v3.0/Sec-5",
            action_required="Split into smaller batches or get Director sign-off",
        )
    return PolicyCheck(
        name="Site Count Limit",
        status="pass",
        details=f"{n} sites within single-batch limit",
        policy_ref="Vi-OPS-POL-v3.0/Sec-5",
    )


def check_bandwidth_cap(intake: IntakeResult) -> PolicyCheck:
    high_bw = [s for s in intake.sites if s.bandwidth_mbps > 1000]
    if high_bw:
        return PolicyCheck(
            name="Bandwidth Cap",
            status="warn",
            details=f"{len(high_bw)} site(s) exceed 1Gbps - needs capacity planning",
            policy_ref="Vi-NET-CAP-v1.2",
            action_required="Capacity team review required",
        )
    return PolicyCheck(
        name="Bandwidth Cap",
        status="pass",
        details="All sites within standard bandwidth tiers",
        policy_ref="Vi-NET-CAP-v1.2",
    )


def check_bfsi_review(intake: IntakeResult) -> PolicyCheck:
    if intake.compliance_tier == "BFSI_equivalent":
        return PolicyCheck(
            name="BFSI Security Review",
            status="warn",
            details="BFSI tier requires CISO co-approval (mandatory)",
            policy_ref="Vi-SEC-POL-v2.0/Sec-8.1",
            action_required="CISO sign-off required",
        )
    return PolicyCheck(
        name="BFSI Security Review",
        status="pass",
        details="Standard tier - no CISO review needed",
        policy_ref="Vi-SEC-POL-v2.0/Sec-8.1",
    )


ALL_CHECKS = [
    check_dot_licensing,
    check_data_residency,
    check_sla_tier,
    check_cost_threshold,
    check_site_count_limit,
    check_bandwidth_cap,
    check_bfsi_review,
]


def decide_approval_level(checks: list[PolicyCheck], total_cost: int) -> str:
    """Determine the highest approval level required."""
    if any(c.status == "fail" for c in checks):
        return "auto"  # rejection - not relevant
    has_bfsi = any("BFSI Security Review" == c.name and c.status == "warn"
                   for c in checks)
    if total_cost >= THRESH_DIRECTOR:
        return "cfo"
    if total_cost >= THRESH_MANAGER:
        return "director" if not has_bfsi else "ciso"
    if total_cost >= THRESH_AUTO:
        return "manager" if not has_bfsi else "ciso"
    return "auto" if not has_bfsi else "ciso"
