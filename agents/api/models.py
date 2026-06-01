"""
Pydantic request/response models for the API.
Kept separate from internal schemas so the wire format stays stable.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    user_request: str = Field(
        min_length=10,
        description="Natural-language customer request",
    )
    customer_name: str = Field(
        default="Unnamed Customer",
        description="Customer name (used for BSS lookup + PDF)",
    )
    deployment_mode: str = Field(
        default="plan_only",
        description="plan_only | apply | destroy (apply/destroy need approval_token)",
    )
    approval_token: Optional[str] = Field(
        default=None,
        description="Required when deployment_mode is apply or destroy",
    )


class WorkflowCreateResponse(BaseModel):
    workflow_id: str
    status: str = "running"
    poll_url: str
    trace_url: str
    pdf_url: Optional[str] = None


class WorkflowSummary(BaseModel):
    workflow_id: str
    customer_name: str
    status: str
    final_decision: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_sec: Optional[float] = None
    site_count: int = 0
    estimated_cost_inr_monthly: Optional[int] = None
    audit_pdf_available: bool = False
    error: Optional[str] = None


class TraceResponse(BaseModel):
    workflow_id: str
    status: str
    trace: list[str]
    finished: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
