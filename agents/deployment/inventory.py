"""
Post-apply inventory collector. Queries AWS via boto3 (tag-filtered to the
workflow) to enumerate exactly what was created. Falls back gracefully when
boto3 is unavailable or AWS is unreachable.
"""

from __future__ import annotations

from typing import Optional

from agents.common.schemas import InfrastructureSummary, SiteInfrastructure

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
    _BOTO_OK = True
except ImportError:
    _BOTO_OK = False


_AWS_REGION = "ap-south-1"
_AWS_PROFILE = "vi-demo"


# Hourly USD pricing snapshot for ap-south-1 (Jun 2026). Used for a coarse
# "burn rate" line so the demo audience can see ongoing cost.
_HOURLY_USD = {
    "vpn_connection": 0.05,
    "transit_gateway": 0.05,
    "tgw_attachment": 0.05,
    "ec2_t3_micro": 0.0114,
    "ec2_t3_medium": 0.0456,
}


def _ec2_client():
    session = boto3.Session(profile_name=_AWS_PROFILE, region_name=_AWS_REGION)
    return session.client("ec2", config=Config(retries={"max_attempts": 3}), verify=False)


def _name_tag(tags: list[dict] | None) -> str:
    if not tags:
        return ""
    for t in tags:
        if t.get("Key") == "Name":
            return t.get("Value", "")
    return ""


def _tag_value(tags: list[dict] | None, key: str) -> str:
    if not tags:
        return ""
    for t in tags:
        if t.get("Key") == key:
            return t.get("Value", "")
    return ""


def _project_filters() -> list[dict]:
    return [{"Name": "tag:Project", "Values": ["ViDemo"]}]


def collect_infrastructure(
    workflow_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> InfrastructureSummary:
    """
    Build an InfrastructureSummary by querying AWS. The workflow_id is currently
    unused (Project tag is enough at our scale) but accepted for future
    workflow-scoped queries.
    """
    notes = list(notes or [])
    summary = InfrastructureSummary(region=_AWS_REGION, notes=notes)

    if not _BOTO_OK:
        notes.append("boto3 unavailable - inventory not collected")
        summary.notes = notes
        return summary

    try:
        ec2 = _ec2_client()
    except Exception as e:  # noqa: BLE001 - any failure here is non-fatal
        notes.append(f"AWS session failed: {type(e).__name__}: {e}")
        summary.notes = notes
        return summary

    counts: dict[str, int] = {}

    def _bump(kind: str, n: int = 1) -> None:
        counts[kind] = counts.get(kind, 0) + n

    # ----- VPCs (central + per-site) -----
    try:
        vpcs = ec2.describe_vpcs(Filters=_project_filters()).get("Vpcs", [])
    except (ClientError, BotoCoreError) as e:
        notes.append(f"describe_vpcs failed: {e}")
        vpcs = []

    site_vpcs: dict[str, dict] = {}  # site_name -> vpc dict
    for v in vpcs:
        name = _name_tag(v.get("Tags"))
        _bump("VPC")
        if name == "vi-demo-central-vpc":
            summary.central_vpc_id = v["VpcId"]
            summary.central_vpc_cidr = v.get("CidrBlock")
        else:
            # site VPC -> derive site_name from "vi-demo-site-{name}-vpc"
            short = name.replace("vi-demo-site-", "").replace("-vpc", "")
            if short:
                site_vpcs[short] = v

    # ----- Subnets, IGWs, RTs, SGs (counts only, plus per-site subnet) -----
    site_subnets: dict[str, str] = {}
    try:
        for s in ec2.describe_subnets(Filters=_project_filters()).get("Subnets", []):
            _bump("Subnet")
            name = _name_tag(s.get("Tags"))
            short = name.replace("vi-demo-site-", "").replace("-subnet", "")
            if short and not name.startswith("vi-demo-central-"):
                site_subnets[short] = s["SubnetId"]
    except (ClientError, BotoCoreError) as e:
        notes.append(f"describe_subnets failed: {e}")

    try:
        igws = ec2.describe_internet_gateways(Filters=_project_filters()).get("InternetGateways", [])
        _bump("Internet Gateway", len(igws))
    except (ClientError, BotoCoreError):
        pass

    try:
        rts = ec2.describe_route_tables(Filters=_project_filters()).get("RouteTables", [])
        _bump("Route Table", len(rts))
    except (ClientError, BotoCoreError):
        pass

    try:
        sgs = ec2.describe_security_groups(Filters=_project_filters()).get("SecurityGroups", [])
        _bump("Security Group", len(sgs))
    except (ClientError, BotoCoreError):
        pass

    # ----- EC2 instances + EIPs (per-site detail) -----
    # Key by the Name-tag-derived short id (matches VPC/VPN/CGW keys).
    site_instances: dict[str, dict] = {}
    try:
        resp = ec2.describe_instances(Filters=_project_filters() + [
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
        ])
        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                _bump("EC2 Instance")
                name = _name_tag(inst.get("Tags"))
                # "vi-demo-site-pune-01-edge" -> "pune-01"
                short = name.replace("vi-demo-site-", "").replace("-edge", "")
                if short:
                    site_instances[short] = inst
    except (ClientError, BotoCoreError) as e:
        notes.append(f"describe_instances failed: {e}")

    try:
        addrs = ec2.describe_addresses(Filters=_project_filters()).get("Addresses", [])
        _bump("Elastic IP", len(addrs))
    except (ClientError, BotoCoreError):
        pass

    # ----- Transit Gateway -----
    try:
        tgws = ec2.describe_transit_gateways(Filters=_project_filters()).get("TransitGateways", [])
        live_tgws = [t for t in tgws if t.get("State") != "deleted"]
        if live_tgws:
            summary.transit_gateway_id = live_tgws[0]["TransitGatewayId"]
            _bump("Transit Gateway", len(live_tgws))
    except (ClientError, BotoCoreError):
        pass

    try:
        tgw_atts = ec2.describe_transit_gateway_attachments(
            Filters=_project_filters()
        ).get("TransitGatewayAttachments", [])
        live = [a for a in tgw_atts if a.get("State") != "deleted"]
        _bump("TGW Attachment", len(live))
    except (ClientError, BotoCoreError):
        pass

    # ----- VPN connections + tunnels (per-site detail) -----
    site_vpns: dict[str, dict] = {}
    try:
        vpns = ec2.describe_vpn_connections(Filters=_project_filters()).get("VpnConnections", [])
        live_vpns = [v for v in vpns if v.get("State") != "deleted"]
        _bump("VPN Connection", len(live_vpns))
        for v in live_vpns:
            name = _name_tag(v.get("Tags"))
            short = name.replace("vi-demo-site-", "").replace("-vpn", "")
            if short:
                site_vpns[short] = v
        # Each VPN has 2 tunnels
        _bump("IPsec Tunnel", len(live_vpns) * 2)
    except (ClientError, BotoCoreError):
        pass

    # ----- Customer Gateways (per-site) -----
    site_cgws: dict[str, dict] = {}
    try:
        cgws = ec2.describe_customer_gateways(Filters=_project_filters()).get("CustomerGateways", [])
        live = [c for c in cgws if c.get("State") != "deleted"]
        _bump("Customer Gateway", len(live))
        for c in live:
            name = _name_tag(c.get("Tags"))
            short = name.replace("vi-demo-site-", "").replace("-cgw", "")
            if short:
                site_cgws[short] = c
    except (ClientError, BotoCoreError):
        pass

    # ----- Assemble per-site detail -----
    site_keys = sorted(set(list(site_vpcs.keys()) + list(site_vpns.keys())))
    for sk in site_keys:
        vpc = site_vpcs.get(sk) or {}
        vpn = site_vpns.get(sk) or {}
        cgw = site_cgws.get(sk) or {}
        inst = site_instances.get(sk) or {}

        telemetry = vpn.get("VgwTelemetry") or []
        t1 = telemetry[0].get("Status") if len(telemetry) > 0 else None
        t2 = telemetry[1].get("Status") if len(telemetry) > 1 else None

        # Friendlier display name from VPN tag (preserves "Pune #01")
        display = _tag_value(vpn.get("Tags"), "Site") or _tag_value(vpc.get("Tags"), "Site") or sk

        summary.sites.append(SiteInfrastructure(
            site_name=display,
            vpc_id=vpc.get("VpcId"),
            vpc_cidr=vpc.get("CidrBlock"),
            subnet_id=site_subnets.get(sk),
            instance_id=inst.get("InstanceId"),
            instance_type=inst.get("InstanceType"),
            public_ip=inst.get("PublicIpAddress"),
            private_ip=inst.get("PrivateIpAddress"),
            customer_gateway_id=cgw.get("CustomerGatewayId"),
            vpn_connection_id=vpn.get("VpnConnectionId"),
            tunnel_1_status=t1,
            tunnel_2_status=t2,
        ))

    # ----- Coarse hourly cost -----
    cost = 0.0
    cost += counts.get("VPN Connection", 0) * _HOURLY_USD["vpn_connection"]
    cost += counts.get("Transit Gateway", 0) * _HOURLY_USD["transit_gateway"]
    cost += counts.get("TGW Attachment", 0) * _HOURLY_USD["tgw_attachment"]
    cost += counts.get("EC2 Instance", 0) * _HOURLY_USD["ec2_t3_micro"]
    summary.cost_per_hour_usd = round(cost, 4) if cost else None

    summary.resource_counts = counts
    summary.total_resources = sum(counts.values())
    summary.notes = notes
    return summary
