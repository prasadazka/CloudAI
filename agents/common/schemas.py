from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class Site(BaseModel):
    city: str = Field(description="City name (e.g., Pune, Bangalore)")
    state: str = Field(default="", description="Indian state if mentioned")
    bandwidth_mbps: int = Field(default=100, description="Bandwidth in Mbps")

    @field_validator("state", mode="before")
    @classmethod
    def _coerce_none_state(cls, v):
        return "" if v is None else v

    @field_validator("bandwidth_mbps", mode="before")
    @classmethod
    def _coerce_none_bw(cls, v):
        return 100 if v is None else v


Intent = Literal[
    "site_onboarding",
    "expansion",
    "modification",
    "decommission",
    "unknown",
]

ComplianceTier = Literal[
    "Standard",
    "BFSI_equivalent",
    "Government",
    "Healthcare",
    "Unknown",
]


CheckStatus = Literal["pass", "warn", "fail"]
OverallStatus = Literal["approved", "approved_with_escalation", "rejected"]
ApprovalLevel = Literal["auto", "manager", "director", "cfo", "ciso"]


class CustomerProfile(BaseModel):
    id: str
    name: str
    tier: Literal["Enterprise_Gold", "Enterprise_Silver", "SMB", "New", "Unknown"]
    since: str = Field(description="ISO date of relationship start")
    total_arr_inr: int = Field(default=0, ge=0)
    industry: str = ""
    primary_contact: str = ""


class ExistingResource(BaseModel):
    type: Literal["vpc", "transit_gateway", "vpn_connection", "subnet", "other"]
    id: str
    region: str
    cidr: Optional[str] = None
    notes: str = ""


class ReuseRecommendation(BaseModel):
    type: Literal["reuse", "skip_create", "expand", "co_locate", "info_only"]
    resource_id: str
    estimated_savings_inr_monthly: int = Field(default=0, ge=0)
    reasoning: str


Topology = Literal[
    "hub_spoke_single_vpn",
    "hub_spoke_dual_vpn",
    "hub_spoke_dual_vpn_bgp",
    "full_mesh_dual_vpn",
]
Complexity = Literal["low", "medium", "high"]


class ArchitectureOption(BaseModel):
    name: str = Field(description="Display name, e.g., 'Option A: Cost-Optimized'")
    topology: Topology
    cost_inr_monthly: int = Field(ge=0)
    resilience_score: float = Field(ge=0.0, le=10.0)
    complexity: Complexity
    sla_uptime_pct: float = Field(ge=0.0, le=100.0)
    tradeoffs: str
    reasoning: str
    recommended: bool = False


class ArchitectureResult(BaseModel):
    options: list[ArchitectureOption]
    recommended_option_name: str
    rationale: str = Field(description="Why this option fits customer + intake")
    summary: str


IaCStatus = Literal[
    "validated",
    "validation_failed",
    "generation_failed",
    "validation_skipped",
]


class TerraformArtifact(BaseModel):
    path: str = Field(description="Relative path of generated file")
    kind: Literal["tf", "tfvars", "yaml", "other"]
    line_count: int = Field(ge=0)


class IaCResult(BaseModel):
    status: IaCStatus
    workflow_dir: str = Field(description="Directory containing generated files")
    artifacts: list[TerraformArtifact] = Field(default_factory=list)
    resources_planned: int = Field(default=0, ge=0)
    self_fix_attempts: int = Field(default=0, ge=0)
    validation_output: str = ""
    error: Optional[str] = None
    diff_summary: str = Field(description="Human-readable summary of what's created")


DeploymentMode = Literal["plan_only", "apply", "destroy"]
DeploymentStatus = Literal[
    "plan_succeeded",
    "plan_failed",
    "applied",
    "applied_with_warnings",
    "apply_failed",
    "destroyed",
    "destroy_failed",
    "skipped_no_approval",
    "skipped_no_terraform",
]
SiteDeploymentStatus = Literal[
    "pending", "creating", "succeeded", "failed", "rolled_back"
]


class SiteInfrastructure(BaseModel):
    """Per-site AWS resources actually created (populated post-apply via boto3)."""
    site_name: str
    vpc_id: Optional[str] = None
    vpc_cidr: Optional[str] = None
    subnet_id: Optional[str] = None
    instance_id: Optional[str] = None
    instance_type: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    customer_gateway_id: Optional[str] = None
    vpn_connection_id: Optional[str] = None
    tunnel_1_status: Optional[str] = None
    tunnel_2_status: Optional[str] = None


class SiteDeployment(BaseModel):
    site_name: str
    status: SiteDeploymentStatus
    duration_sec: float = Field(default=0.0, ge=0.0)
    retries: int = Field(default=0, ge=0)
    error: Optional[str] = None


class InfrastructureSummary(BaseModel):
    """Aggregate AWS inventory created for the workflow."""
    region: str = "ap-south-1"
    transit_gateway_id: Optional[str] = None
    central_vpc_id: Optional[str] = None
    central_vpc_cidr: Optional[str] = None
    resource_counts: dict[str, int] = Field(default_factory=dict)
    total_resources: int = 0
    sites: list[SiteInfrastructure] = Field(default_factory=list)
    cost_per_hour_usd: Optional[float] = None
    notes: list[str] = Field(default_factory=list)


class DeploymentResult(BaseModel):
    mode: DeploymentMode
    status: DeploymentStatus
    workflow_dir: str
    sites_total: int = Field(default=0, ge=0)
    sites_succeeded: int = Field(default=0, ge=0)
    sites_failed: int = Field(default=0, ge=0)
    sites_detail: list[SiteDeployment] = Field(default_factory=list)
    total_duration_sec: float = Field(default=0.0, ge=0.0)
    rollback_triggered: bool = False
    terraform_output_tail: str = Field(default="", description="Last ~120 lines of terraform stdout")
    approval_token: Optional[str] = None
    summary: str = ""
    infrastructure: Optional[InfrastructureSummary] = None


TestOutcome = Literal["pass", "fail", "borderline", "skipped"]
ValidationStatus = Literal[
    "all_pass",
    "pass_with_warnings",
    "some_failed",
    "all_failed",
    "tests_skipped",
]
ValidationMode = Literal["real", "simulated", "skipped"]


class SiteTest(BaseModel):
    name: Literal["ping", "throughput", "qos", "encryption"]
    outcome: TestOutcome
    measured: str = Field(description="Human-readable measured value")
    target: str = Field(description="Target / SLA threshold")
    notes: str = ""


class SiteValidation(BaseModel):
    site_name: str
    overall: TestOutcome
    tests: list[SiteTest] = Field(default_factory=list)


class ValidationResult(BaseModel):
    status: ValidationStatus
    mode: ValidationMode
    sla_target_uptime_pct: float = Field(default=99.5, ge=0.0, le=100.0)
    sites_tested: int = Field(default=0, ge=0)
    sites_passed: int = Field(default=0, ge=0)
    sites_borderline: int = Field(default=0, ge=0)
    sites_failed: int = Field(default=0, ge=0)
    sites_detail: list[SiteValidation] = Field(default_factory=list)
    summary: str = ""
    disclaimer: Optional[str] = Field(
        default=None,
        description="Transparency note when results are simulated, not measured",
    )


class DiscoveryResult(BaseModel):
    customer_found: bool
    customer_profile: Optional[CustomerProfile] = None
    existing_resources: list[ExistingResource] = Field(default_factory=list)
    active_vpn_count: int = 0
    recommendations: list[ReuseRecommendation] = Field(default_factory=list)
    recent_incidents_90d: int = 0
    total_estimated_savings_inr_monthly: int = 0
    summary: str = Field(description="One-line discovery summary")


class PolicyCheck(BaseModel):
    name: str = Field(description="Check name, e.g., 'DOT Licensing'")
    status: CheckStatus
    details: str = Field(description="Human-readable explanation")
    policy_ref: str = Field(default="", description="Internal policy reference")
    action_required: Optional[str] = Field(default=None)


class PolicyResult(BaseModel):
    overall_status: OverallStatus
    approval_level_required: ApprovalLevel
    checks: list[PolicyCheck]
    estimated_cost_inr_monthly: int = Field(ge=0)
    blocking_violations: list[str] = Field(default_factory=list)
    summary: str = Field(description="One-line business summary of the decision")


class IntakeResult(BaseModel):
    intent: Intent = Field(description="Primary intent of the request")
    sites: list[Site] = Field(default_factory=list, description="List of sites")
    site_count: int = Field(default=0, description="Total site count")
    connectivity_type: str = Field(
        default="SD-WAN",
        description="Type: SD-WAN, MPLS, VPN, Direct Connect",
    )
    qos_apps: list[str] = Field(
        default_factory=list,
        description="Apps needing priority: SAP, CCTV, VoIP, etc.",
    )
    compliance_tier: ComplianceTier = Field(
        default="Standard",
        description="Compliance level required",
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Deadline as ISO date (YYYY-MM-DD) if mentioned",
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence 0.0-1.0",
    )
    needs_clarification: bool = Field(
        default=False,
        description="True if request is ambiguous",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Question to ask user if clarification needed",
    )
    raw_request: str = Field(description="Original user input")
