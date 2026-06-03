"""
Simulated test results - generates plausible E2E test outputs based on
chosen architecture. Used when real deployment is not available.

Numbers based on real SD-WAN benchmarks for similar topologies.
"""

import random

from agents.common.schemas import (
    ArchitectureOption,
    IntakeResult,
    SiteTest,
    SiteValidation,
    Topology,
)


# Tuned expected ranges per topology
PROFILES: dict[str, dict] = {
    "hub_spoke_single_vpn": {
        "latency_ms_range": (35, 75),
        "throughput_pct_range": (80, 95),
        "qos_works": False,
        "encryption_works": True,
    },
    "hub_spoke_dual_vpn": {
        "latency_ms_range": (20, 45),
        "throughput_pct_range": (90, 98),
        "qos_works": True,
        "encryption_works": True,
    },
    "hub_spoke_dual_vpn_bgp": {
        "latency_ms_range": (12, 28),
        "throughput_pct_range": (94, 99),
        "qos_works": True,
        "encryption_works": True,
    },
    "full_mesh_dual_vpn": {
        "latency_ms_range": (8, 22),
        "throughput_pct_range": (96, 100),
        "qos_works": True,
        "encryption_works": True,
    },
}


# Per-tier latency SLA target (ms)
SLA_LATENCY_TARGETS = {
    "BFSI_equivalent": 30,
    "Government": 30,
    "Healthcare": 35,
    "Standard": 50,
    "Unknown": 50,
}


def _ping_test(profile: dict, bandwidth: int, sla_target_ms: int) -> SiteTest:
    lo, hi = profile["latency_ms_range"]
    measured = random.uniform(lo, hi)
    if measured <= sla_target_ms:
        outcome = "pass"
    elif measured <= sla_target_ms * 1.2:
        outcome = "borderline"
    else:
        outcome = "fail"
    return SiteTest(
        name="ping",
        outcome=outcome,
        measured=f"{measured:.1f}ms (p99)",
        target=f"<={sla_target_ms}ms",
        notes="Latency from site SD-WAN edge to central VPC",
    )


def _throughput_test(profile: dict, bandwidth: int) -> SiteTest:
    lo, hi = profile["throughput_pct_range"]
    pct = random.uniform(lo, hi)
    measured_mbps = bandwidth * pct / 100
    if pct >= 90:
        outcome = "pass"
    elif pct >= 80:
        outcome = "borderline"
    else:
        outcome = "fail"
    return SiteTest(
        name="throughput",
        outcome=outcome,
        measured=f"{measured_mbps:.0f} Mbps ({pct:.0f}% of provisioned)",
        target=f">={int(bandwidth * 0.9)} Mbps (90% of {bandwidth})",
        notes="iperf3 across IPsec tunnel",
    )


def _qos_test(profile: dict) -> SiteTest:
    if profile["qos_works"]:
        return SiteTest(
            name="qos",
            outcome="pass",
            measured="DSCP EF preserved for priority apps",
            target="EF/AF41 markings preserved end-to-end",
            notes="SAP + CCTV traffic correctly prioritized under load",
        )
    return SiteTest(
        name="qos",
        outcome="fail",
        measured="DSCP markings stripped at tunnel ingress",
        target="EF/AF41 markings preserved end-to-end",
        notes="Single-VPN topology cannot guarantee QoS - upgrade required for SLA",
    )


def _encryption_test(profile: dict) -> SiteTest:
    if profile["encryption_works"]:
        return SiteTest(
            name="encryption",
            outcome="pass",
            measured="AES-256-SHA2 IPsec ESP (sample capture)",
            target="AES-128 or stronger, no plaintext",
            notes="ESP packets verified - no clear-text leakage",
        )
    return SiteTest(
        name="encryption",
        outcome="fail",
        measured="ESP missing on tunnel 2",
        target="AES-128 or stronger, no plaintext",
        notes="Investigation required",
    )


def _aggregate_outcome(tests: list[SiteTest]) -> str:
    """
    A site's connectivity is determined by ping + throughput + encryption.
    QoS is a feature, not a connectivity test — its failure does NOT mean
    the site is down. Architecturally-known QoS limits (e.g. single-VPN
    topology can't preserve DSCP) should not flip the whole site to failed.
    """
    CRITICAL = {"ping", "throughput", "encryption"}
    critical_outcomes = {t.outcome for t in tests if t.name in CRITICAL}
    feature_outcomes = {t.outcome for t in tests if t.name not in CRITICAL}

    if "fail" in critical_outcomes:
        return "fail"
    if "borderline" in critical_outcomes:
        return "borderline"
    if "fail" in feature_outcomes:
        # Connectivity good, but a feature (QoS) is not delivered.
        # Borderline so the user sees something needs attention without
        # concluding the deployment is broken.
        return "borderline"
    return "pass"


def simulate_site_tests(
    intake: IntakeResult,
    recommended_option: ArchitectureOption,
    seed: int | None = None,
) -> list[SiteValidation]:
    """Generate simulated tests for each site based on chosen topology."""
    if seed is not None:
        random.seed(seed)

    profile = PROFILES.get(
        recommended_option.topology,
        PROFILES["hub_spoke_dual_vpn"],
    )
    sla_target_ms = SLA_LATENCY_TARGETS.get(intake.compliance_tier, 50)

    results: list[SiteValidation] = []
    for s in intake.sites:
        tests = [
            _ping_test(profile, s.bandwidth_mbps, sla_target_ms),
            _throughput_test(profile, s.bandwidth_mbps),
            _qos_test(profile),
            _encryption_test(profile),
        ]
        overall = _aggregate_outcome(tests)
        results.append(SiteValidation(
            site_name=s.city,
            overall=overall,
            tests=tests,
        ))
    return results
