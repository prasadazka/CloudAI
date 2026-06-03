import { Clock, FileCheck, Network, ShieldCheck, Sparkles } from "lucide-react";

import { Card, CardBody } from "@/components/ui/Card";
import { WorkflowForm } from "@/components/WorkflowForm";

const STATS = [
  { num: "< 4h", label: "Median time to live" },
  { num: "9", label: "Specialist agents" },
  { num: "99.5%", label: "Uptime SLA target" },
  { num: "BFSI", label: "Audit-ready output" },
];

const PIPELINE = [
  "Intake",
  "Discovery",
  "Policy",
  "Architecture",
  "IaC",
  "Deploy",
  "Validate",
  "Audit",
];

const TRUST = [
  {
    Icon: Network,
    title: "Deterministic Terraform",
    body: "Curated modules — no LLM-generated infrastructure, no hallucinated resources.",
  },
  {
    Icon: ShieldCheck,
    title: "Human-in-the-loop approval",
    body: "Edit cost, bandwidth, compliance tier before a single AWS call. Token-gated apply.",
  },
  {
    Icon: FileCheck,
    title: "Cryptographic audit trail",
    body: "Every workflow ships a vendor-attested PDF with provisioned-resource manifest.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-8 lg:grid lg:grid-cols-12 lg:gap-10 lg:space-y-0">
      {/* HERO — full width on mobile, 7 cols on lg, 8 on xl */}
      <section className="lg:col-span-7 xl:col-span-8">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-vi-yellow/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-vi-red">
          <Sparkles className="h-3 w-3" />
          Agentic AI · Cloud Orchestration
        </div>

        <h1 className="text-3xl font-bold leading-[1.05] tracking-tight text-zinc-900 sm:text-4xl lg:text-5xl xl:text-6xl">
          Production-grade cloud,
          <br />
          <span className="text-vi-red">orchestrated in hours.</span>
        </h1>

        <p className="mt-4 max-w-2xl text-base leading-relaxed text-zinc-600 sm:mt-5 sm:text-lg">
          Sutradhar converts natural-language service requests into compliant,
          audited AWS deployments. Nine specialist agents enforce policy,
          render hardened Terraform, apply under human approval, and emit a
          board-ready compliance report — collapsing the six-week enterprise
          onboarding cycle into a single afternoon.
        </p>

        {/* KPI strip */}
        <dl className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-zinc-200 bg-zinc-200 sm:grid-cols-4">
          {STATS.map(({ num, label }) => (
            <div key={label} className="bg-white px-4 py-4 sm:px-5 sm:py-5">
              <dd className="text-xl font-semibold tracking-tight text-vi-red sm:text-2xl">
                {num}
              </dd>
              <dt className="mt-1 text-xs text-zinc-500">{label}</dt>
            </div>
          ))}
        </dl>

        {/* Trust pillars */}
        <ul className="mt-7 grid gap-3 sm:grid-cols-3 sm:gap-4">
          {TRUST.map(({ Icon, title, body }) => (
            <li
              key={title}
              className="rounded-lg border border-zinc-200 bg-white p-3.5 transition hover:border-vi-red/40"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <Icon className="h-4 w-4 text-vi-red" />
                <p className="text-xs font-semibold uppercase tracking-wider text-zinc-800">
                  {title}
                </p>
              </div>
              <p className="text-[11px] leading-relaxed text-zinc-600">
                {body}
              </p>
            </li>
          ))}
        </ul>

        {/* Pipeline preview — desktop only */}
        <div className="mt-10 hidden lg:block">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Supervised nine-agent pipeline
          </p>
          <div className="flex flex-wrap items-center gap-1 text-xs text-zinc-500">
            {PIPELINE.map((step, i) => (
              <div key={step} className="flex items-center gap-1">
                <span className="rounded-full bg-white px-2.5 py-1 font-medium ring-1 ring-zinc-200">
                  {step}
                </span>
                {i < PIPELINE.length - 1 && (
                  <span className="text-zinc-300">→</span>
                )}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-zinc-400">
            Each agent emits a typed contract; Supervisor routes on conditional state.
          </p>
        </div>
      </section>

      {/* FORM — full width on mobile, 5 cols on lg, 4 on xl */}
      <aside className="lg:col-span-5 xl:col-span-4">
        <Card className="lg:sticky lg:top-24">
          <CardBody className="p-5 sm:p-6">
            <div className="mb-1.5 inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-vi-red">
              <Clock className="h-3 w-3" />
              Begin a deployment
            </div>
            <h2 className="text-xl font-semibold leading-tight text-zinc-900 sm:text-2xl">
              Submit a service request
            </h2>
            <p className="mt-1.5 mb-5 text-sm leading-relaxed text-zinc-500 sm:mb-6">
              Supervisor decomposes intent across nine specialists and surfaces
              an editable plan. No AWS resource is created until you approve.
            </p>
            <WorkflowForm />
          </CardBody>
        </Card>
      </aside>
    </div>
  );
}
