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
