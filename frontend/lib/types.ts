// Mirrors backend Pydantic models for type-safety on the wire.

export type DeploymentMode = "plan_only" | "apply" | "destroy";

export interface WorkflowCreateRequest {
  user_request: string;
  customer_name: string;
  deployment_mode?: DeploymentMode;
  approval_token?: string;
}

export interface WorkflowCreateResponse {
  workflow_id: string;
  status: string;
  poll_url: string;
  trace_url: string;
  pdf_url?: string;
}

export type WorkflowStatus =
  | "running"
  | "awaiting_approval"
  | "applying"
  | "deployed"
  | "destroying"
  | "destroyed"
  | "completed"
  | "errored";

export interface WorkflowSummary {
  workflow_id: string;
  customer_name: string;
  status: WorkflowStatus;
  final_decision:
    | "approved_auto"
    | "approved_with_escalation"
    | "rejected"
    | "clarification_needed"
    | "error"
    | null;
  started_at: string;
  finished_at?: string | null;
  duration_sec?: number | null;
  site_count: number;
  estimated_cost_inr_monthly?: number | null;
  audit_pdf_available: boolean;
  error?: string | null;
}

export interface SiteOverride {
  city: string;
  bandwidth_mbps?: number;
}

export interface WorkflowOverrides {
  sites?: SiteOverride[];
  connectivity_type?: string;
  compliance_tier?: string;
  qos_apps?: string[];
}

export interface ApproveDeployRequest {
  approval_token: string;
  mode: "apply" | "destroy";
  overrides?: WorkflowOverrides;
}

export interface ApproveDeployResponse {
  workflow_id: string;
  status: string;
  mode: string;
  message: string;
}

export interface TraceResponse {
  workflow_id: string;
  status: string;
  trace: string[];
  finished: boolean;
}

// ---- Full agent results (mirrors backend Pydantic) ----

export interface SiteOut {
  city: string;
  state: string;
  bandwidth_mbps: number;
}

export interface IntakeOut {
  intent: string;
  sites: SiteOut[];
  site_count: number;
  connectivity_type: string;
  qos_apps: string[];
  compliance_tier: string;
  deadline?: string | null;
  confidence: number;
  needs_clarification: boolean;
  clarification_question?: string | null;
  raw_request: string;
}

export interface ExistingResourceOut {
  type: string;
  id: string;
  region: string;
  cidr?: string | null;
  notes: string;
}

export interface ReuseRecommendationOut {
  type: string;
  resource_id: string;
  estimated_savings_inr_monthly: number;
  reasoning: string;
}

export interface DiscoveryOut {
  customer_found: boolean;
  customer_profile?: {
    id: string;
    name: string;
    tier: string;
    since: string;
    total_arr_inr: number;
    industry: string;
    primary_contact: string;
  };
  existing_resources: ExistingResourceOut[];
  active_vpn_count: number;
  recommendations: ReuseRecommendationOut[];
  recent_incidents_90d: number;
  total_estimated_savings_inr_monthly: number;
  summary: string;
}

export interface PolicyCheckOut {
  name: string;
  status: "pass" | "warn" | "fail";
  details: string;
  policy_ref: string;
  action_required?: string | null;
}

export interface PolicyOut {
  overall_status: string;
  approval_level_required: string;
  checks: PolicyCheckOut[];
  estimated_cost_inr_monthly: number;
  blocking_violations: string[];
  summary: string;
}

export interface ArchitectureOptionOut {
  name: string;
  topology: string;
  cost_inr_monthly: number;
  resilience_score: number;
  complexity: string;
  sla_uptime_pct: number;
  tradeoffs: string;
  reasoning: string;
  recommended: boolean;
}

export interface ArchitectureOut {
  options: ArchitectureOptionOut[];
  recommended_option_name: string;
  rationale: string;
  summary: string;
}

export interface IaCArtifactOut {
  path: string;
  kind: string;
  line_count: number;
}

export interface IaCOut {
  status: string;
  workflow_dir: string;
  artifacts: IaCArtifactOut[];
  resources_planned: number;
  self_fix_attempts: number;
  validation_output: string;
  error?: string | null;
  diff_summary: string;
}

export interface SiteInfrastructureOut {
  site_name: string;
  vpc_id?: string | null;
  vpc_cidr?: string | null;
  subnet_id?: string | null;
  instance_id?: string | null;
  instance_type?: string | null;
  public_ip?: string | null;
  private_ip?: string | null;
  customer_gateway_id?: string | null;
  vpn_connection_id?: string | null;
  tunnel_1_status?: string | null;
  tunnel_2_status?: string | null;
}

export interface InfrastructureSummaryOut {
  region: string;
  transit_gateway_id?: string | null;
  central_vpc_id?: string | null;
  central_vpc_cidr?: string | null;
  resource_counts: Record<string, number>;
  total_resources: number;
  sites: SiteInfrastructureOut[];
  cost_per_hour_usd?: number | null;
  notes: string[];
}

export interface DeploymentOut {
  mode: string;
  status: string;
  workflow_dir: string;
  sites_total: number;
  sites_succeeded: number;
  sites_failed: number;
  sites_detail: { site_name: string; status: string }[];
  total_duration_sec: number;
  rollback_triggered: boolean;
  terraform_output_tail: string;
  summary: string;
  infrastructure?: InfrastructureSummaryOut | null;
}

export interface ValidationSiteTestOut {
  name: string;
  outcome: "pass" | "fail" | "borderline" | "skipped";
  measured: string;
  target: string;
  notes: string;
}

export interface ValidationSiteOut {
  site_name: string;
  overall: "pass" | "fail" | "borderline" | "skipped";
  tests: ValidationSiteTestOut[];
}

export interface ValidationOut {
  status: string;
  mode: string;
  sla_target_uptime_pct: number;
  sites_tested: number;
  sites_passed: number;
  sites_borderline: number;
  sites_failed: number;
  sites_detail: ValidationSiteOut[];
  summary: string;
  disclaimer?: string | null;
}

export interface FullWorkflow {
  workflow_id: string;
  status: string;
  customer_name: string;
  user_request: string;
  final_decision?: string | null;
  audit_pdf_available: boolean;
  intake: IntakeOut | null;
  discovery: DiscoveryOut | null;
  policy: PolicyOut | null;
  architecture: ArchitectureOut | null;
  iac: IaCOut | null;
  deployment: DeploymentOut | null;
  validation: ValidationOut | null;
}
