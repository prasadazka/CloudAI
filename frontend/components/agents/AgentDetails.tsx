"use client";

import { useState } from "react";
import { Check, AlertTriangle, Copy, Minus, X } from "lucide-react";

import type {
  ArchitectureOut,
  DeploymentOut,
  DiscoveryOut,
  FullWorkflow,
  IaCOut,
  InfrastructureSummaryOut,
  IntakeOut,
  PolicyOut,
  ValidationOut,
} from "@/lib/types";

import type { AgentKey } from "./agentMeta";

interface Props {
  agent: AgentKey;
  full: FullWorkflow | null;
}

function fmtRs(n?: number | null): string {
  if (n == null) return "—";
  if (n >= 1_00_00_000) return `Rs ${(n / 1_00_00_000).toFixed(2)}Cr`;
  if (n >= 1_00_000) return `Rs ${(n / 1_00_000).toFixed(2)}L`;
  return `Rs ${n.toLocaleString("en-IN")}`;
}

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function onCopy(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for older browsers / non-secure contexts
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* swallow */
      }
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={onCopy}
      title={`${label} to clipboard`}
      aria-label={`${label} to clipboard`}
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium transition ${
        copied
          ? "border-success bg-success-soft text-success"
          : "border-zinc-300 bg-white text-zinc-600 hover:border-vi-red hover:text-vi-red"
      }`}
    >
      {copied ? <Check className="h-3 w-3" strokeWidth={3} /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : label}
    </button>
  );
}


function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === "pass") return <Check className="h-3.5 w-3.5 text-success" />;
  if (s === "warn" || s === "borderline")
    return <AlertTriangle className="h-3.5 w-3.5 text-warning" />;
  if (s === "fail") return <X className="h-3.5 w-3.5 text-danger" />;
  return <Minus className="h-3.5 w-3.5 text-zinc-400" />;
}

const Table = ({ children }: { children: React.ReactNode }) => (
  <div className="overflow-x-auto rounded-md border border-zinc-200">
    <table className="w-full text-xs">{children}</table>
  </div>
);
const Th = ({ children }: { children: React.ReactNode }) => (
  <th className="bg-zinc-50 px-2.5 py-2 text-left font-medium text-zinc-600">
    {children}
  </th>
);
const Td = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <td className={`px-2.5 py-2 align-top text-zinc-700 ${className}`}>{children}</td>
);

// ── Intake ───────────────────────────────────────────────────────────────
function IntakeDetails({ d }: { d: IntakeOut }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <KV label="Intent" value={d.intent} />
        <KV label="Confidence" value={`${(d.confidence * 100).toFixed(0)}%`} />
        <KV label="Connectivity" value={d.connectivity_type} />
        <KV label="Tier" value={d.compliance_tier} />
        {d.deadline && <KV label="Deadline" value={d.deadline} />}
        {d.qos_apps.length > 0 && (
          <KV label="Priority Apps" value={d.qos_apps.join(", ")} />
        )}
      </div>
      {d.sites.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>#</Th>
              <Th>City</Th>
              <Th>State</Th>
              <Th>Bandwidth</Th>
            </tr>
          </thead>
          <tbody>
            {d.sites.map((s, i) => (
              <tr key={i} className="border-t border-zinc-200">
                <Td>{i + 1}</Td>
                <Td className="font-medium text-zinc-900">{s.city}</Td>
                <Td>{s.state || "—"}</Td>
                <Td>{s.bandwidth_mbps} Mbps</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}

// ── Discovery ────────────────────────────────────────────────────────────
function DiscoveryDetails({ d }: { d: DiscoveryOut }) {
  return (
    <div className="space-y-3">
      {d.customer_profile && (
        <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <KV label="Customer ID" value={d.customer_profile.id} />
          <KV label="Tier" value={d.customer_profile.tier} />
          <KV label="Since" value={d.customer_profile.since} />
          <KV label="ARR" value={fmtRs(d.customer_profile.total_arr_inr)} />
          <KV label="Industry" value={d.customer_profile.industry || "—"} />
          <KV label="Active VPNs" value={String(d.active_vpn_count)} />
        </div>
      )}
      {d.existing_resources.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-zinc-600">Existing resources</p>
          <Table>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th>ID</Th>
                <Th>CIDR</Th>
                <Th>Notes</Th>
              </tr>
            </thead>
            <tbody>
              {d.existing_resources.map((r, i) => (
                <tr key={i} className="border-t border-zinc-200">
                  <Td className="font-medium text-zinc-900">{r.type}</Td>
                  <Td className="font-mono text-[11px]">{r.id}</Td>
                  <Td>{r.cidr || "—"}</Td>
                  <Td>{r.notes}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
      {d.recommendations.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-zinc-600">
            Reuse recommendations — total savings {fmtRs(d.total_estimated_savings_inr_monthly)}/month
          </p>
          <Table>
            <thead>
              <tr>
                <Th>Action</Th>
                <Th>Resource</Th>
                <Th>Savings</Th>
                <Th>Reasoning</Th>
              </tr>
            </thead>
            <tbody>
              {d.recommendations.map((r, i) => (
                <tr key={i} className="border-t border-zinc-200">
                  <Td>
                    <span className="rounded-full bg-vi-yellow/20 px-2 py-0.5 text-[10px] font-medium uppercase text-vi-red">
                      {r.type.replace("_", " ")}
                    </span>
                  </Td>
                  <Td className="font-mono text-[11px]">{r.resource_id}</Td>
                  <Td className="font-medium text-vi-red">
                    {fmtRs(r.estimated_savings_inr_monthly)}/mo
                  </Td>
                  <Td>{r.reasoning}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
}

// ── Policy ───────────────────────────────────────────────────────────────
function PolicyDetails({ d }: { d: PolicyOut }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <KV label="Decision" value={d.overall_status.replace(/_/g, " ")} />
        <KV label="Approval" value={d.approval_level_required.toUpperCase()} />
        <KV label="Cost/month" value={fmtRs(d.estimated_cost_inr_monthly)} />
        <KV label="Cost/year" value={fmtRs(d.estimated_cost_inr_monthly * 12)} />
      </div>
      <Table>
        <thead>
          <tr>
            <Th>Check</Th>
            <Th>Status</Th>
            <Th>Details</Th>
            <Th>Policy Ref</Th>
          </tr>
        </thead>
        <tbody>
          {d.checks.map((c, i) => (
            <tr key={i} className="border-t border-zinc-200">
              <Td className="font-medium text-zinc-900">{c.name}</Td>
              <Td>
                <span className="inline-flex items-center gap-1">
                  <StatusIcon status={c.status} />
                  {c.status.toUpperCase()}
                </span>
              </Td>
              <Td>
                {c.details}
                {c.action_required && (
                  <div className="mt-1 text-[10px] italic text-zinc-500">
                    → {c.action_required}
                  </div>
                )}
              </Td>
              <Td className="whitespace-nowrap font-mono text-[10px]">
                {c.policy_ref || "—"}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

// ── Architecture ─────────────────────────────────────────────────────────
function ArchitectureDetails({ d }: { d: ArchitectureOut }) {
  return (
    <div className="space-y-3">
      <p className="text-xs italic text-zinc-600">{d.rationale}</p>
      <div className="grid gap-2 sm:grid-cols-3">
        {d.options.map((o) => (
          <div
            key={o.name}
            className={[
              "rounded-md border p-3 text-xs",
              o.recommended
                ? "border-vi-red bg-vi-red/5"
                : "border-zinc-200 bg-white",
            ].join(" ")}
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold text-zinc-900">{o.name}</p>
              {o.recommended && (
                <span className="rounded-full bg-vi-red px-1.5 py-0.5 text-[9px] font-medium uppercase text-white">
                  Recommended
                </span>
              )}
            </div>
            <p className="mt-0.5 font-mono text-[10px] text-zinc-500">{o.topology}</p>
            <dl className="mt-2 space-y-1 text-[11px]">
              <div className="flex justify-between">
                <dt className="text-zinc-500">Cost</dt>
                <dd className="font-medium">{fmtRs(o.cost_inr_monthly)}/mo</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">SLA</dt>
                <dd className="font-medium">{o.sla_uptime_pct}%</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Resilience</dt>
                <dd className="font-medium">{o.resilience_score}/10</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-zinc-500">Complexity</dt>
                <dd className="font-medium">{o.complexity}</dd>
              </div>
            </dl>
            <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
              {o.tradeoffs}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── IaC ──────────────────────────────────────────────────────────────────
function IaCDetails({ d }: { d: IaCOut }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <KV label="Status" value={d.status.replace(/_/g, " ")} />
        <KV label="Resources planned" value={String(d.resources_planned)} />
        <KV label="Self-fix attempts" value={String(d.self_fix_attempts)} />
        <KV label="Files" value={String(d.artifacts.length)} />
      </div>
      <p className="text-xs text-zinc-600">{d.diff_summary}</p>
      <Table>
        <thead>
          <tr>
            <Th>File</Th>
            <Th>Kind</Th>
            <Th>Lines</Th>
          </tr>
        </thead>
        <tbody>
          {d.artifacts.map((a, i) => (
            <tr key={i} className="border-t border-zinc-200">
              <Td className="font-mono text-[11px]">{a.path}</Td>
              <Td>{a.kind}</Td>
              <Td>{a.line_count}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

// ── Deployment ───────────────────────────────────────────────────────────
function DeploymentDetails({ d }: { d: DeploymentOut }) {
  const failed =
    d.status.includes("failed") ||
    d.status === "skipped_no_terraform" ||
    d.status === "skipped_no_approval";

  // Extract any Error lines from the captured output for prominent display
  const errorLines = (d.terraform_output_tail || "")
    .split("\n")
    .filter((l) => /\b(error|failed|cannot|denied|invalid)\b/i.test(l))
    .slice(0, 6);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <KV label="Mode" value={d.mode} />
        <KV label="Status" value={d.status.replace(/_/g, " ")} />
        <KV label="Duration" value={`${d.total_duration_sec.toFixed(1)}s`} />
        <KV label="Succeeded" value={`${d.sites_succeeded}/${d.sites_total}`} />
      </div>
      <p className="text-xs text-zinc-700">{d.summary}</p>

      {failed && errorLines.length > 0 && (
        <div className="rounded-md border border-danger/40 bg-danger-soft p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-danger">
              Terraform reported the following errors:
            </p>
            <CopyButton text={errorLines.join("\n")} label="Copy errors" />
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-danger">
            {errorLines.join("\n")}
          </pre>
        </div>
      )}

      {d.sites_detail && d.sites_detail.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Site</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {d.sites_detail.map((s, i) => (
              <tr key={i} className="border-t border-zinc-200">
                <Td className="font-medium text-zinc-900">{s.site_name}</Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={s.status === "succeeded" ? "pass" : s.status === "failed" ? "fail" : "warn"} />
                    {s.status}
                  </span>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      {d.infrastructure && <InfrastructureInventory infra={d.infrastructure} />}

      {d.terraform_output_tail && (
        <details
          className="rounded-md border border-zinc-200 bg-zinc-50"
          open={failed}
        >
          <summary className="flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-zinc-700">
            <span>terraform output (last lines)</span>
            <CopyButton text={d.terraform_output_tail} label="Copy log" />
          </summary>
          <pre className="overflow-x-auto whitespace-pre-wrap px-3 pb-3 font-mono text-[10px] leading-relaxed text-zinc-700">
            {d.terraform_output_tail}
          </pre>
        </details>
      )}
    </div>
  );
}

// ── Infrastructure Inventory (post-apply boto3 snapshot) ─────────────────
function InfrastructureInventory({ infra }: { infra: InfrastructureSummaryOut }) {
  const counts = infra.resource_counts || {};
  const sortedKinds = Object.keys(counts).sort();
  const inrPerHour = infra.cost_per_hour_usd != null
    ? Math.round(infra.cost_per_hour_usd * 83)
    : null;

  function tunnelBadge(s?: string | null) {
    if (!s) return <span className="text-zinc-400">—</span>;
    if (s === "UP") return <span className="rounded bg-success-soft px-1.5 py-0.5 text-[10px] font-semibold text-success">UP</span>;
    return <span className="rounded bg-danger-soft px-1.5 py-0.5 text-[10px] font-semibold text-danger">{s}</span>;
  }

  return (
    <details className="rounded-md border-2 border-vi-red/30 bg-white" open>
      <summary className="flex cursor-pointer items-center justify-between gap-2 bg-vi-red/5 px-3 py-2 text-xs font-semibold text-zinc-800">
        <span>Infrastructure Created on AWS · {infra.total_resources} resources · {infra.region}</span>
        {inrPerHour != null && (
          <span className="text-[11px] font-normal text-zinc-600">
            Burn rate: ~Rs {inrPerHour}/hr (${infra.cost_per_hour_usd}/hr)
          </span>
        )}
      </summary>

      <div className="space-y-3 p-3">
        {/* Hub */}
        {(infra.transit_gateway_id || infra.central_vpc_id) && (
          <div className="rounded border border-zinc-200 bg-zinc-50 p-2">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Hub</p>
            <div className="grid grid-cols-1 gap-1 text-[11px] sm:grid-cols-3">
              {infra.transit_gateway_id && (
                <div><span className="text-zinc-500">Transit Gateway:</span> <code className="font-mono text-zinc-900">{infra.transit_gateway_id}</code></div>
              )}
              {infra.central_vpc_id && (
                <div><span className="text-zinc-500">Central VPC:</span> <code className="font-mono text-zinc-900">{infra.central_vpc_id}</code></div>
              )}
              {infra.central_vpc_cidr && (
                <div><span className="text-zinc-500">CIDR:</span> <code className="font-mono text-zinc-900">{infra.central_vpc_cidr}</code></div>
              )}
            </div>
          </div>
        )}

        {/* Resource type counts */}
        {sortedKinds.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Resource Type Breakdown</p>
            <div className="flex flex-wrap gap-1.5">
              {sortedKinds.map((k) => (
                <span key={k} className="rounded border border-zinc-300 bg-white px-2 py-0.5 text-[10px]">
                  <span className="font-semibold text-zinc-900">{counts[k]}</span>
                  <span className="ml-1 text-zinc-600">{k}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Per-site detail */}
        {infra.sites && infra.sites.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-600">Per-Site Details</p>
            <div className="overflow-x-auto">
              <Table>
                <thead>
                  <tr>
                    <Th>Site</Th>
                    <Th>VPC / CIDR</Th>
                    <Th>EC2</Th>
                    <Th>Public IP</Th>
                    <Th>VPN</Th>
                    <Th>Tun-1</Th>
                    <Th>Tun-2</Th>
                  </tr>
                </thead>
                <tbody>
                  {infra.sites.map((s, i) => (
                    <tr key={i} className="border-t border-zinc-200">
                      <Td className="font-medium text-zinc-900">{s.site_name}</Td>
                      <Td className="font-mono text-[10px]">
                        {s.vpc_id || "—"}<br />
                        <span className="text-zinc-500">{s.vpc_cidr || ""}</span>
                      </Td>
                      <Td className="font-mono text-[10px]">
                        {s.instance_id || "—"}<br />
                        <span className="text-zinc-500">{s.instance_type || ""}</span>
                      </Td>
                      <Td className="font-mono text-[10px]">{s.public_ip || "—"}</Td>
                      <Td className="font-mono text-[10px]">{s.vpn_connection_id || "—"}</Td>
                      <Td>{tunnelBadge(s.tunnel_1_status)}</Td>
                      <Td>{tunnelBadge(s.tunnel_2_status)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </div>
        )}

        {infra.notes && infra.notes.length > 0 && (
          <div className="rounded border border-warning/40 bg-warning-soft px-2 py-1.5 text-[10px] text-zinc-700">
            {infra.notes.map((n, i) => <div key={i}>· {n}</div>)}
          </div>
        )}
      </div>
    </details>
  );
}

// ── Validation ───────────────────────────────────────────────────────────
function ValidationDetails({ d }: { d: ValidationOut }) {
  // Aggregate feature-level outcomes across sites so the user can see
  // *why* something is borderline (usually QoS on cheap topologies).
  const featureNotes: Record<string, Set<string>> = {};
  d.sites_detail.forEach((s) =>
    s.tests
      .filter((t) => t.outcome === "fail" || t.outcome === "borderline")
      .forEach((t) => {
        if (!featureNotes[t.name]) featureNotes[t.name] = new Set();
        if (t.notes) featureNotes[t.name].add(t.notes);
      }),
  );

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <KV label="Mode" value={d.mode} />
        <KV label="SLA target" value={`${d.sla_target_uptime_pct}%`} />
        <KV label="Passed" value={`${d.sites_passed}/${d.sites_tested}`} />
        <KV
          label="Failed"
          value={
            d.sites_failed > 0
              ? String(d.sites_failed)
              : d.sites_borderline > 0
              ? `0 (${d.sites_borderline} borderline)`
              : "0"
          }
        />
      </div>

      {d.disclaimer && (
        <p className="rounded-md bg-warning-soft px-3 py-2 text-[11px] italic text-warning">
          ⓘ {d.disclaimer}
        </p>
      )}

      {Object.keys(featureNotes).length > 0 && (
        <div className="space-y-1 rounded-md border border-zinc-200 bg-zinc-50 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600">
            Why some tests didn't pass
          </p>
          {Object.entries(featureNotes).map(([name, notes]) => (
            <div key={name} className="text-[11px] leading-relaxed text-zinc-700">
              <span className="font-semibold capitalize">{name}:</span>{" "}
              {Array.from(notes).join(" • ")}
            </div>
          ))}
        </div>
      )}

      <Table>
        <thead>
          <tr>
            <Th>Site</Th>
            <Th>Overall</Th>
            <Th>Ping</Th>
            <Th>Throughput</Th>
            <Th>QoS</Th>
            <Th>Encryption</Th>
          </tr>
        </thead>
        <tbody>
          {d.sites_detail.map((s, i) => {
            const t = (n: string) => s.tests.find((x) => x.name === n);
            const ping = t("ping");
            const tp = t("throughput");
            const qos = t("qos");
            const enc = t("encryption");
            return (
              <tr key={i} className="border-t border-zinc-200">
                <Td className="font-medium text-zinc-900">{s.site_name}</Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={s.overall} />
                    {s.overall.toUpperCase()}
                  </span>
                </Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={ping?.outcome ?? "skipped"} />
                    {ping?.measured ?? "—"}
                  </span>
                </Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={tp?.outcome ?? "skipped"} />
                    {tp?.measured ?? "—"}
                  </span>
                </Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={qos?.outcome ?? "skipped"} />
                  </span>
                </Td>
                <Td>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={enc?.outcome ?? "skipped"} />
                  </span>
                </Td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </div>
  );
}

// ── KV ───────────────────────────────────────────────────────────────────
function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-0.5 truncate text-xs font-medium text-zinc-900">{value}</div>
    </div>
  );
}

// ── Main router ──────────────────────────────────────────────────────────
export function AgentDetails({ agent, full }: Props) {
  if (!full) {
    return (
      <div className="rounded-md bg-zinc-50 p-3 text-xs text-zinc-500">
        Loading details…
      </div>
    );
  }

  if (agent === "Intake" && full.intake) return <IntakeDetails d={full.intake} />;
  if (agent === "Discovery" && full.discovery) return <DiscoveryDetails d={full.discovery} />;
  if (agent === "Policy" && full.policy) return <PolicyDetails d={full.policy} />;
  if (agent === "Architecture" && full.architecture)
    return <ArchitectureDetails d={full.architecture} />;
  if (agent === "IaC" && full.iac) return <IaCDetails d={full.iac} />;
  if (agent === "Deployment" && full.deployment)
    return <DeploymentDetails d={full.deployment} />;
  if (agent === "Validation" && full.validation)
    return <ValidationDetails d={full.validation} />;
  if (agent === "Audit") {
    return (
      <div className="text-xs text-zinc-600">
        Compliance PDF generated. Use the <strong>Download Audit PDF</strong> button
        on the right to retrieve the Sutradhar audit report.
      </div>
    );
  }

  return (
    <div className="rounded-md bg-zinc-50 p-3 text-xs text-zinc-500">
      No additional details available.
    </div>
  );
}
