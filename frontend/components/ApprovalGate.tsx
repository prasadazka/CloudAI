"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Lock,
  Network,
  Pencil,
  RotateCcw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  FullWorkflow,
  PolicyCheckOut,
  WorkflowOverrides,
  WorkflowSummary,
} from "@/lib/types";

import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "./ui/Card";

interface Props {
  workflowId: string;
  summary: WorkflowSummary | null;
  full: FullWorkflow | null;
  onApproved: () => void;
}

interface EditableRow {
  city: string;
  state: string;
  bandwidth_mbps: number;
  originalBw: number;
}

const CONNECTIVITY_OPTIONS = ["SD-WAN", "MPLS", "VPN", "Direct Connect"] as const;
const TIER_OPTIONS = [
  "Standard",
  "BFSI_equivalent",
  "Government",
  "Healthcare",
] as const;

// Approval window — matches enterprise NOC SOP (15 minutes).
const APPROVAL_WINDOW_MS = 15 * 60 * 1000;

// Cost model — mirrors agents/policy/rules.py exactly so client preview matches.
const BASE_COST_PER_SITE = 80_000;
const COST_PER_MBPS = 500;
const MPLS_MULTIPLIER = 1.8;
const DX_MULTIPLIER = 2.0; // Direct Connect surcharge
const COMPLIANCE_MULTIPLIER: Record<string, number> = {
  Standard: 1.0,
  BFSI_equivalent: 1.25,
  Government: 1.3,
  Healthcare: 1.2,
};

function estimateCost(
  rows: EditableRow[],
  connectivity: string,
  compliance: string,
): number {
  return rows.reduce((sum, r) => {
    let c = BASE_COST_PER_SITE + r.bandwidth_mbps * COST_PER_MBPS;
    const conn = connectivity.toUpperCase();
    if (conn === "MPLS") c *= MPLS_MULTIPLIER;
    else if (conn === "DIRECT CONNECT") c *= DX_MULTIPLIER;
    c *= COMPLIANCE_MULTIPLIER[compliance] ?? 1.0;
    return sum + Math.round(c);
  }, 0);
}

function fmtMMSS(ms: number): string {
  if (ms <= 0) return "0:00";
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtL(n?: number | null): string {
  if (n == null) return "—";
  if (n >= 1_00_00_000) return `Rs ${(n / 1_00_00_000).toFixed(2)}Cr`;
  return `Rs ${(n / 1_00_000).toFixed(2)}L`;
}

interface ResourceCategory {
  label: string;
  count: number;
  note: string;
}

/** Per-site resource model derived from terraform/modules/branch_site/main.tf */
function computeResourceBreakdown(siteCount: number): ResourceCategory[] {
  const sites = Math.max(siteCount, 1);
  return [
    { label: "Transit Gateway + attachments", count: 2, note: "Central network hub" },
    { label: "VPCs", count: 1 + sites, note: "1 central + 1 per site" },
    { label: "Subnets", count: 2 + sites, note: "2 central + 1 per site" },
    { label: "Internet Gateways", count: 1 + sites, note: "1 per VPC" },
    { label: "Route tables + associations", count: 4 + 2 * sites, note: "Routing per VPC" },
    { label: "VPN Connections", count: sites, note: "1 per site (dual-tunnel each)" },
    { label: "Customer Gateways", count: sites, note: "1 per site, points at EIP" },
    { label: "EC2 SD-WAN Edges", count: sites, note: "t3.micro, strongSwan via cloud-init" },
    { label: "Elastic IPs", count: sites, note: "Static public IP per edge" },
    { label: "Security Groups", count: sites, note: "IPsec + ESP rules" },
    { label: "IAM roles + instance profiles", count: 3 * sites, note: "SSM + VPN-describe permissions" },
    { label: "TGW routes", count: sites, note: "Site CIDR → VPN attachment" },
  ];
}

export function ApprovalGate({ workflowId, summary, full, onApproved }: Props) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"apply" | "destroy">("apply");
  const [token, setToken] = useState("NOC-APPROVED-V1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllResources, setShowAllResources] = useState(false);

  // Editable state for review surface
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [connectivity, setConnectivity] = useState<string>("");
  const [origConnectivity, setOrigConnectivity] = useState<string>("");
  const [tier, setTier] = useState<string>("");
  const [origTier, setOrigTier] = useState<string>("");

  // Hydrate editable state when full data arrives.
  useEffect(() => {
    if (!full?.intake) return;
    setRows(
      full.intake.sites.map((s) => ({
        city: s.city,
        state: s.state || "",
        bandwidth_mbps: s.bandwidth_mbps,
        originalBw: s.bandwidth_mbps,
      })),
    );
    setConnectivity(full.intake.connectivity_type);
    setOrigConnectivity(full.intake.connectivity_type);
    setTier(full.intake.compliance_tier);
    setOrigTier(full.intake.compliance_tier);
  }, [full?.workflow_id]);

  // ---- All hooks must run before any conditional return ----
  const sites = full?.intake?.sites ?? [];
  const siteCount = sites.length || summary?.site_count || 0;
  const resources = useMemo(
    () => computeResourceBreakdown(siteCount),
    [siteCount],
  );

  // Approval timer — counts down from when planning finished.
  const expiryAt = useMemo(() => {
    const finished = summary?.finished_at
      ? new Date(summary.finished_at).getTime()
      : Date.now();
    return finished + APPROVAL_WINDOW_MS;
  }, [summary?.finished_at]);

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (summary?.status !== "awaiting_approval") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [summary?.status]);

  const remainingMs = Math.max(0, expiryAt - now);
  const expired = summary?.status === "awaiting_approval" && remainingMs === 0;

  // Live cost recalculation (matches backend formula exactly)
  const liveCost = useMemo(() => {
    if (rows.length === 0) return null;
    return estimateCost(rows, connectivity || "SD-WAN", tier || "Standard");
  }, [rows, connectivity, tier]);
  const originalCost = full?.policy?.estimated_cost_inr_monthly ?? null;
  const costDelta =
    liveCost != null && originalCost != null ? liveCost - originalCost : null;

  if (!summary) return null;

  const status = summary.status;
  const isAwaiting = status === "awaiting_approval";
  const isDeployed = status === "deployed";
  const isApplying = status === "applying";
  const isDestroying = status === "destroying";
  const isDestroyed = status === "destroyed";
  const isErrored = status === "errored";

  if (!isAwaiting && !isDeployed && !isApplying && !isDestroying && !isDestroyed && !isErrored)
    return null;

  const cost =
    full?.policy?.estimated_cost_inr_monthly ??
    summary.estimated_cost_inr_monthly ??
    0;
  const recommended = full?.architecture?.options.find((o) => o.recommended);
  const totalResources = full?.iac?.resources_planned ?? 0;
  const checks: PolicyCheckOut[] = full?.policy?.checks ?? [];
  const passed = checks.filter((c) => c.status === "pass").length;
  const warns = checks.filter((c) => c.status === "warn").length;
  const fails = checks.filter((c) => c.status === "fail").length;

  const resourceTotal = resources.reduce((s, r) => s + r.count, 0);
  const visibleResources = showAllResources ? resources : resources.slice(0, 6);

  const bwChanged = rows.some((r) => r.bandwidth_mbps !== r.originalBw);
  const connectivityChanged = connectivity && connectivity !== origConnectivity;
  const tierChanged = tier && tier !== origTier;
  const anyEdited = bwChanged || connectivityChanged || tierChanged;

  function buildOverrides(): WorkflowOverrides | undefined {
    if (!anyEdited) return undefined;
    const out: WorkflowOverrides = {};
    if (bwChanged) {
      out.sites = rows
        .filter((r) => r.bandwidth_mbps !== r.originalBw)
        .map((r) => ({ city: r.city, bandwidth_mbps: r.bandwidth_mbps }));
    }
    if (connectivityChanged) out.connectivity_type = connectivity;
    if (tierChanged) out.compliance_tier = tier;
    return out;
  }

  function resetEdits() {
    if (!full?.intake) return;
    setRows((rs) =>
      rs.map((r) => ({ ...r, bandwidth_mbps: r.originalBw })),
    );
    setConnectivity(origConnectivity);
    setTier(origTier);
  }

  function applyBulkBandwidth(mbps: number) {
    setRows((rs) => rs.map((r) => ({ ...r, bandwidth_mbps: mbps })));
  }

  function openModal(m: "apply" | "destroy") {
    setMode(m);
    setError(null);
    setOpen(true);
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const overrides = mode === "apply" ? buildOverrides() : undefined;
      await api.approveDeploy(workflowId, {
        approval_token: token,
        mode,
        overrides,
      });
      setOpen(false);
      setBusy(false);
      onApproved();
    } catch (e: any) {
      setError(e?.message || "Approval failed");
      setBusy(false);
    }
  }

  return (
    <>
      <Card
        className={
          isAwaiting
            ? "border-vi-yellow/50 bg-gradient-to-br from-vi-yellow/10 to-white"
            : isDeployed
            ? "border-success/30 bg-success-soft/30"
            : isErrored
            ? "border-danger/40 bg-danger-soft/40"
            : "border-vi-red/30 bg-vi-red/5"
        }
      >
        <CardHeader
          className={
            isAwaiting
              ? "border-vi-yellow/40"
              : isDeployed
              ? "border-success/30"
              : isErrored
              ? "border-danger/30"
              : "border-vi-red/30"
          }
        >
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              {isAwaiting && (
                <>
                  <ShieldCheck className="h-5 w-5 text-vi-red" />
                  Review &amp; approve deployment
                </>
              )}
              {isApplying && (
                <>
                  <span className="h-2 w-2 animate-pulse-dot rounded-full bg-vi-red" />
                  Deploying to AWS Mumbai…
                </>
              )}
              {isDeployed && (
                <>
                  <Check className="h-5 w-5 text-success" />
                  Infrastructure deployed
                </>
              )}
              {isDestroying && (
                <>
                  <span className="h-2 w-2 animate-pulse-dot rounded-full bg-warning" />
                  Destroying infrastructure…
                </>
              )}
              {isDestroyed && (
                <>
                  <Trash2 className="h-5 w-5 text-zinc-500" />
                  Destroyed
                </>
              )}
              {isErrored && (
                <>
                  <AlertCircle className="h-5 w-5 text-danger" />
                  Apply failed — partial infrastructure
                </>
              )}
            </CardTitle>
            {isAwaiting && <ApprovalTimer ms={remainingMs} />}
            {isErrored && (
              <span className="shrink-0 rounded-md bg-danger-soft px-2 py-1 text-xs font-semibold text-danger ring-1 ring-danger/30">
                Cleanup required
              </span>
            )}
          </div>
        </CardHeader>

        <CardBody className="space-y-5 p-4 sm:p-5">
          {isAwaiting && (
            <>
              <p className="text-sm leading-relaxed text-zinc-700">
                Plan complete. Below is everything that will be created in AWS
                if you approve. <strong className="text-vi-red">Nothing has been provisioned yet.</strong>
              </p>

              {/* Headline stats — Monthly cost updates live as user edits */}
              <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Sites" value={String(siteCount)} />
                <Stat label="AWS resources" value={`~${totalResources || resourceTotal}`} />
                <LiveCostStat
                  label="Monthly cost"
                  liveValue={liveCost ?? cost}
                  originalValue={originalCost ?? cost}
                  delta={costDelta}
                />
                <Stat label="Annual cost" value={fmtL((liveCost ?? cost) * 12)} />
              </dl>

              {/* Resource breakdown */}
              <section>
                <SectionHeader
                  icon={<Network className="h-4 w-4" />}
                  title="What will be created on AWS"
                  subtitle="Real resources, not mocks. Region: ap-south-1 (Mumbai)"
                />
                <div className="rounded-md border border-zinc-200 bg-white">
                  <ul className="divide-y divide-zinc-100">
                    {visibleResources.map((r) => (
                      <li key={r.label} className="flex items-center justify-between gap-3 px-3 py-2.5">
                        <div className="min-w-0">
                          <p className="truncate text-xs font-medium text-zinc-900">{r.label}</p>
                          <p className="truncate text-[11px] text-zinc-500">{r.note}</p>
                        </div>
                        <span className="shrink-0 rounded-md bg-zinc-50 px-2 py-0.5 text-xs font-semibold tabular-nums text-zinc-900 ring-1 ring-zinc-200">
                          {r.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {resources.length > 6 && (
                    <button
                      type="button"
                      onClick={() => setShowAllResources((s) => !s)}
                      className="flex w-full items-center justify-center gap-1 border-t border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-medium text-vi-red hover:bg-zinc-100"
                    >
                      {showAllResources ? (
                        <>
                          <ChevronDown className="h-3.5 w-3.5" />
                          Hide {resources.length - 6} more
                        </>
                      ) : (
                        <>
                          <ChevronRight className="h-3.5 w-3.5" />
                          Show {resources.length - 6} more categories
                        </>
                      )}
                    </button>
                  )}
                </div>
              </section>

              {/* Global config — editable */}
              <section>
                <SectionHeader
                  title="Service parameters"
                  subtitle="Inferred from your request. Edit before approving if you want different."
                />
                <div className="grid gap-3 sm:grid-cols-3">
                  <EditableField label="Connectivity type">
                    <select
                      aria-label="Connectivity type"
                      value={connectivity}
                      onChange={(e) => setConnectivity(e.target.value)}
                      className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm focus:border-vi-red focus:outline-none focus:ring-1 focus:ring-vi-red"
                    >
                      {CONNECTIVITY_OPTIONS.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                    {connectivityChanged && <ChangedBadge />}
                  </EditableField>
                  <EditableField label="Compliance tier">
                    <select
                      aria-label="Compliance tier"
                      value={tier}
                      onChange={(e) => setTier(e.target.value)}
                      className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm focus:border-vi-red focus:outline-none focus:ring-1 focus:ring-vi-red"
                    >
                      {TIER_OPTIONS.map((o) => (
                        <option key={o} value={o}>
                          {o.replace("_", " ")}
                        </option>
                      ))}
                    </select>
                    {tierChanged && <ChangedBadge />}
                  </EditableField>
                  <EditableField label="AWS region">
                    <div className="flex items-center gap-1.5 rounded-md border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 text-sm text-zinc-600">
                      <Lock className="h-3 w-3" />
                      ap-south-1 (Mumbai)
                    </div>
                  </EditableField>
                </div>
              </section>

              {/* Sites — editable bandwidth */}
              {rows.length > 0 && (
                <section>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <SectionHeader
                      title={`Sites — ${rows.length}`}
                      subtitle="VPC CIDR and BGP ASN auto-allocated. Bandwidth defaults to 100 Mbps unless specified."
                    />
                    <div className="flex items-center gap-1.5 text-[11px]">
                      <span className="text-zinc-500">Quick set all:</span>
                      {[50, 100, 200, 500, 1000].map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => applyBulkBandwidth(v)}
                          className="rounded-full border border-zinc-300 bg-white px-2 py-0.5 font-medium text-zinc-700 hover:border-vi-red hover:text-vi-red"
                        >
                          {v}M
                        </button>
                      ))}
                      {anyEdited && (
                        <button
                          type="button"
                          onClick={resetEdits}
                          className="ml-1 inline-flex items-center gap-1 text-zinc-500 hover:text-vi-red"
                        >
                          <RotateCcw className="h-3 w-3" />
                          reset
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="overflow-x-auto rounded-md border border-zinc-200 bg-white">
                    <table className="w-full text-xs">
                      <thead className="bg-zinc-50 text-left">
                        <tr>
                          <th className="px-3 py-2 font-medium text-zinc-600">#</th>
                          <th className="px-3 py-2 font-medium text-zinc-600">City</th>
                          <th className="px-3 py-2 font-medium text-zinc-600">State</th>
                          <th className="px-3 py-2 font-medium text-zinc-600">
                            Bandwidth <span className="text-zinc-400 font-normal">(editable)</span>
                          </th>
                          <th className="px-3 py-2 font-medium text-zinc-600">
                            VPC CIDR <Lock className="ml-0.5 inline-block h-3 w-3 text-zinc-400" />
                          </th>
                          <th className="px-3 py-2 font-medium text-zinc-600">
                            BGP ASN <Lock className="ml-0.5 inline-block h-3 w-3 text-zinc-400" />
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r, i) => {
                          const changed = r.bandwidth_mbps !== r.originalBw;
                          return (
                            <tr key={i} className="border-t border-zinc-100">
                              <td className="px-3 py-2 text-zinc-500">{i + 1}</td>
                              <td className="px-3 py-2 font-medium text-zinc-900">{r.city}</td>
                              <td className="px-3 py-2 text-zinc-700">{r.state || "—"}</td>
                              <td className="px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  <input
                                    type="number"
                                    aria-label={`Bandwidth for ${r.city} in Mbps`}
                                    title={`Bandwidth for ${r.city}`}
                                    min={10}
                                    max={10000}
                                    step={10}
                                    value={r.bandwidth_mbps}
                                    onChange={(e) => {
                                      const v = Math.max(
                                        10,
                                        Math.min(10000, Number(e.target.value) || 100),
                                      );
                                      setRows((rs) =>
                                        rs.map((row, idx) =>
                                          idx === i ? { ...row, bandwidth_mbps: v } : row,
                                        ),
                                      );
                                    }}
                                    className={`w-20 rounded-md border px-2 py-1 font-mono text-xs focus:border-vi-red focus:outline-none focus:ring-1 focus:ring-vi-red ${
                                      changed
                                        ? "border-vi-red bg-vi-red/5"
                                        : "border-zinc-200 bg-white"
                                    }`}
                                  />
                                  <span className="text-[10px] text-zinc-500">Mbps</span>
                                  {changed && (
                                    <span className="text-[9px] font-medium uppercase text-vi-red">
                                      changed
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="px-3 py-2 font-mono text-[11px] text-zinc-500">
                                10.{i + 1}.0.0/16
                              </td>
                              <td className="px-3 py-2 font-mono text-[11px] text-zinc-500">
                                {65000 + i + 1}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  {anyEdited && (
                    <p className="mt-2 flex items-center gap-1.5 text-[11px] text-vi-red">
                      <Pencil className="h-3 w-3" />
                      Edits will be applied when you click Approve & Deploy. IaC
                      will be regenerated automatically.
                    </p>
                  )}
                </section>
              )}

              {/* Architecture */}
              {recommended && (
                <section>
                  <SectionHeader title="Recommended architecture" />
                  <div className="rounded-md border border-vi-red/40 bg-vi-red/5 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-zinc-900">{recommended.name}</p>
                      <span className="rounded-full bg-vi-red px-2 py-0.5 text-[10px] font-medium uppercase text-white">
                        Selected
                      </span>
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] text-zinc-500">
                      {recommended.topology}
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] sm:grid-cols-4">
                      <Pair label="SLA" value={`${recommended.sla_uptime_pct}%`} />
                      <Pair label="Resilience" value={`${recommended.resilience_score}/10`} />
                      <Pair label="Complexity" value={recommended.complexity} />
                      <Pair label="Cost" value={`${fmtL(recommended.cost_inr_monthly)}/mo`} />
                    </div>
                    <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">
                      {recommended.tradeoffs}
                    </p>
                  </div>
                </section>
              )}

              {/* Compliance summary */}
              {checks.length > 0 && (
                <section>
                  <SectionHeader title={`Compliance — ${passed} pass, ${warns} warn, ${fails} fail`} />
                  <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {checks.map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5"
                      >
                        <StatusGlyph status={c.status} />
                        <div className="min-w-0">
                          <p className="truncate text-xs font-medium text-zinc-900">{c.name}</p>
                          <p className="truncate text-[10px] text-zinc-500">{c.details}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Warning — duration + cost scale with actual site count.
                  Cost formula: $0.05/hr per VPN + $0.05/hr TGW + $0.05/hr TGW
                  attachment + $0.0114/hr per t3.micro EC2. Inr at ~83/USD. */}
              {(() => {
                const applyEta =
                  siteCount <= 2 ? "5-8 min"
                    : siteCount <= 5 ? "8-12 min"
                    : siteCount <= 10 ? "15-25 min"
                    : "25-40 min";
                const usdPerHour =
                  0.05 * siteCount + 0.05 + 0.05 + 0.0114 * siteCount;
                const inrPerHour = Math.max(1, Math.round(usdPerHour * 83));
                return (
                  <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-xs leading-relaxed text-warning">
                    <p className="flex items-start gap-2">
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>
                        Real <code className="rounded bg-white px-1 py-0.5 text-[10px]">terraform apply</code> takes
                        <strong> {applyEta}</strong> for {siteCount} site{siteCount === 1 ? "" : "s"}.
                        AWS billing (~Rs {inrPerHour}/hr) starts once tunnels come up.
                        Use the Destroy button afterwards to stop charges.
                      </span>
                    </p>
                  </div>
                );
              })()}

              {/* Expired callout */}
              {expired && (
                <div className="rounded-md border border-danger/40 bg-danger-soft p-4">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-danger">
                        Approval window expired
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-zinc-700">
                        For security, plan approvals must be acted on within 15
                        minutes. The plan is preserved but you'll need to
                        re-validate before applying. Costs may have changed.
                      </p>
                      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                        <Link href="/">
                          <Button variant="secondary" size="sm">
                            <X className="h-3.5 w-3.5" />
                            Back to home
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 sm:flex-row sm:justify-end">
                <Link href="/" className="sm:order-1">
                  <Button variant="secondary" size="lg" className="w-full sm:w-auto">
                    <X className="h-4 w-4" />
                    Hold for now
                  </Button>
                </Link>
                <Button
                  size="lg"
                  onClick={() => openModal("apply")}
                  disabled={expired}
                  className="sm:order-2"
                >
                  <ShieldCheck className="h-4 w-4" />
                  {expired ? "Approval expired" : "Approve & Deploy"}
                </Button>
              </div>
            </>
          )}

          {isApplying && (
            <p className="text-sm leading-relaxed text-zinc-700">
              Provisioning real AWS resources. About{" "}
              <strong>
                {siteCount <= 2
                  ? "5-7 minutes"
                  : siteCount <= 5
                  ? "8-12 minutes"
                  : "15-25 minutes"}
              </strong>{" "}
              for {siteCount} VPN tunnel{siteCount === 1 ? "" : "s"}. Watch live
              activity below.
            </p>
          )}
          {isDestroying && (
            <DestroyProgress
              workflowId={workflowId}
              siteCount={siteCount}
              resourceCount={totalResources || resourceTotal}
            />
          )}

          {isDeployed && (
            <>
              <p className="text-sm leading-relaxed text-zinc-700">
                All sites are operational. AWS billing is active. Destroy when
                done to stop charges.
              </p>
              <Button
                size="lg"
                variant="secondary"
                onClick={() => openModal("destroy")}
                className="w-full sm:w-auto"
              >
                <Trash2 className="h-4 w-4" />
                Destroy infrastructure
              </Button>
            </>
          )}

          {isDestroyed && (
            <div className="space-y-3">
              <p className="text-sm leading-relaxed text-zinc-700">
                ✓ Infrastructure has been removed. No further charges.
              </p>
              <Link href="/">
                <Button variant="secondary" size="sm">
                  Back to home
                </Button>
              </Link>
            </div>
          )}

          {isErrored && (
            <div className="space-y-4">
              <p className="text-sm leading-relaxed text-zinc-700">
                <code className="rounded bg-white px-1.5 py-0.5 text-xs ring-1 ring-zinc-200">
                  terraform apply
                </code>{" "}
                failed before completing all sites. Some AWS resources may have
                been created and are still billing. <strong className="text-danger">Clean them up now.</strong>
              </p>

              {/* Show deployment summary if available */}
              {full?.deployment && (
                <div className="rounded-md border border-zinc-200 bg-white p-3 text-xs">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                    Last attempt
                  </p>
                  <p className="text-zinc-700">{full.deployment.summary}</p>
                  <p className="mt-1 font-mono text-[10px] text-zinc-500">
                    Status: {full.deployment.status} ·{" "}
                    {full.deployment.total_duration_sec.toFixed(0)}s elapsed
                  </p>
                </div>
              )}

              <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-xs leading-relaxed text-warning">
                <p className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    Cleanup runs <code className="rounded bg-white px-1 py-0.5 text-[10px]">terraform destroy</code>{" "}
                    against this workflow's state. Takes 2-8 minutes depending
                    on how much was created. <strong>Recommended immediately</strong>{" "}
                    to stop AWS billing.
                  </span>
                </p>
              </div>

              <div className="flex flex-col gap-2 border-t border-zinc-200 pt-4 sm:flex-row sm:justify-end">
                <Link href="/" className="sm:order-1">
                  <Button variant="secondary" size="lg" className="w-full sm:w-auto">
                    Leave for later
                  </Button>
                </Link>
                <Button
                  size="lg"
                  onClick={() => openModal("destroy")}
                  variant="danger"
                  className="sm:order-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Clean up partial infrastructure
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Modal */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-card-hover">
            <div className="border-b border-zinc-200 px-5 py-4">
              <h3 className="text-h3 font-semibold text-zinc-900">
                Confirm {mode === "apply" ? "deployment" : "destruction"}
              </h3>
              <p className="mt-1 text-sm text-zinc-500">
                {mode === "apply"
                  ? "Real AWS resources will be created. Charges begin immediately."
                  : "All AWS resources for this workflow will be deleted."}
              </p>
            </div>
            <div className="space-y-3 px-5 py-4">
              <label className="block text-xs font-medium text-zinc-700">
                Approval token
                <input
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 font-mono text-sm focus:border-vi-red focus:outline-none focus:ring-2 focus:ring-vi-red/20"
                  placeholder="NOC-APPROVED-V1"
                />
              </label>
              {error && (
                <p className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger">
                  {error}
                </p>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-zinc-200 px-5 py-3">
              <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
                Cancel
              </Button>
              <Button
                onClick={confirm}
                disabled={busy || !token.trim()}
                variant={mode === "destroy" ? "danger" : "primary"}
              >
                {busy
                  ? "Submitting…"
                  : mode === "apply"
                  ? "Confirm deploy"
                  : "Confirm destroy"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white px-3 py-2.5 ring-1 ring-zinc-200">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-zinc-900">{value}</div>
    </div>
  );
}

function LiveCostStat({
  label,
  liveValue,
  originalValue,
  delta,
}: {
  label: string;
  liveValue: number;
  originalValue: number;
  delta: number | null;
}) {
  const changed = delta !== null && Math.abs(delta) > 0;
  return (
    <div
      className={`rounded-md px-3 py-2.5 ring-1 ${
        changed
          ? "bg-vi-red/5 ring-vi-red/30"
          : "bg-white ring-zinc-200"
      }`}
    >
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <div className={`text-sm font-semibold ${changed ? "text-vi-red" : "text-zinc-900"}`}>
          {fmtL(liveValue)}
        </div>
        {changed && (
          <div className="flex items-center gap-0.5 text-[10px] font-medium text-zinc-500">
            <span className="line-through">{fmtL(originalValue)}</span>
            {delta! > 0 ? (
              <ArrowUp className="h-2.5 w-2.5 text-vi-red" />
            ) : (
              <ArrowDown className="h-2.5 w-2.5 text-success" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Live destruction progress — polls /trace and counts "Destruction complete" events. */
function DestroyProgress({
  workflowId,
  siteCount,
  resourceCount,
}: {
  workflowId: string;
  siteCount: number;
  resourceCount: number;
}) {
  const [destroyed, setDestroyed] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [startedAt] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const r = await fetch(`/api/workflows/${workflowId}/trace`);
        const data = await r.json();
        if (cancelled) return;
        const lines: string[] = data.trace || [];
        const count = lines.filter((l) => /Destruction complete/i.test(l)).length;
        setDestroyed(count);
        setElapsed(Math.floor((Date.now() - startedAt) / 1000));
      } catch {
        /* ignore */
      }
      if (!cancelled) timer = setTimeout(tick, 2000);
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [workflowId, startedAt]);

  const total = Math.max(resourceCount, 1);
  const pct = Math.min(100, Math.round((destroyed / total) * 100));
  const eta = siteCount <= 2 ? 180 : 600;
  const remaining = Math.max(0, eta - elapsed);
  const mm = Math.floor(remaining / 60);
  const ss = remaining % 60;

  return (
    <div className="space-y-3">
      <p className="text-sm leading-relaxed text-zinc-700">
        Tearing down AWS resources. Approximately{" "}
        <strong>{siteCount <= 2 ? "2-3 minutes" : "5-10 minutes"}</strong> for{" "}
        {resourceCount} resources. Live progress below.
      </p>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between text-xs">
          <span className="font-medium text-zinc-700">
            {destroyed} of ~{resourceCount} resources removed
          </span>
          <span className="font-mono text-zinc-500">
            {pct}% · ~{mm}:{ss.toString().padStart(2, "0")} remaining
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200">
          <div
            className={`h-full bg-warning transition-all ${
              pct >= 95 ? "w-full"
              : pct >= 85 ? "w-[90%]"
              : pct >= 70 ? "w-[75%]"
              : pct >= 55 ? "w-[60%]"
              : pct >= 40 ? "w-[45%]"
              : pct >= 25 ? "w-[30%]"
              : pct >= 10 ? "w-[15%]"
              : pct >= 1  ? "w-[5%]"
              : "w-0"
            }`}
          />
        </div>
        <p className="text-[10px] text-zinc-500">
          Elapsed: {Math.floor(elapsed / 60)}:{(elapsed % 60).toString().padStart(2, "0")}
        </p>
      </div>
    </div>
  );
}


function ApprovalTimer({ ms }: { ms: number }) {
  const seconds = Math.ceil(ms / 1000);
  const total = 15 * 60;
  const pct = Math.max(0, Math.min(100, (seconds / total) * 100));

  let tone: { text: string; ring: string; dot: string };
  if (ms <= 0) {
    tone = { text: "text-danger", ring: "ring-danger/40 bg-danger-soft", dot: "bg-danger" };
  } else if (ms <= 60_000) {
    tone = { text: "text-danger", ring: "ring-danger/40 bg-danger-soft", dot: "bg-danger animate-pulse-dot" };
  } else if (ms <= 3 * 60_000) {
    tone = { text: "text-warning", ring: "ring-warning/40 bg-warning-soft", dot: "bg-warning" };
  } else {
    tone = { text: "text-success", ring: "ring-success/30 bg-success-soft", dot: "bg-success" };
  }

  return (
    <div
      className={`shrink-0 rounded-md px-2.5 py-1.5 text-xs ring-1 ${tone.ring}`}
      title="Approval window remaining"
    >
      <div className="flex items-center gap-1.5">
        <Clock className={`h-3.5 w-3.5 ${tone.text}`} />
        <span className={`font-mono font-semibold tabular-nums ${tone.text}`}>
          {fmtMMSS(ms)}
        </span>
        <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
      </div>
      <div
        className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-white/60"
        aria-label="Approval window remaining"
      >
        <div
          className={`h-full transition-all ${
            ms <= 60_000 ? "bg-danger" : ms <= 3 * 60_000 ? "bg-warning" : "bg-success"
          } ${
            pct > 90 ? "w-full"
            : pct > 75 ? "w-[85%]"
            : pct > 60 ? "w-[70%]"
            : pct > 45 ? "w-[55%]"
            : pct > 30 ? "w-[40%]"
            : pct > 15 ? "w-[25%]"
            : pct > 5  ? "w-[10%]"
            : "w-0"
          }`}
        />
      </div>
    </div>
  );
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-white px-2 py-1 ring-1 ring-zinc-200">
      <span className="text-[9px] uppercase tracking-wider text-zinc-500">{label}: </span>
      <span className="font-semibold text-zinc-900">{value}</span>
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-700">
        {icon}
        {title}
      </div>
      {subtitle && <p className="mt-0.5 text-[11px] text-zinc-500">{subtitle}</p>}
    </div>
  );
}

function EditableField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">
        {label}
      </span>
      <div className="relative">{children}</div>
    </label>
  );
}

function ChangedBadge() {
  return (
    <span className="absolute -top-1.5 right-0 rounded-full bg-vi-red px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider text-white">
      Changed
    </span>
  );
}

function StatusGlyph({ status }: { status: string }) {
  if (status === "pass")
    return (
      <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-success/10 text-success">
        <Check className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    );
  if (status === "warn")
    return (
      <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
        <AlertCircle className="h-2.5 w-2.5" />
      </span>
    );
  if (status === "fail")
    return (
      <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
        <X className="h-2.5 w-2.5" strokeWidth={3} />
      </span>
    );
  return <span className="mt-0.5 h-4 w-4 shrink-0 rounded-full bg-zinc-200" />;
}
