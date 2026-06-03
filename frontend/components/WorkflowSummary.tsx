"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, Coins, MapPin } from "lucide-react";

import { api } from "@/lib/api";
import type { WorkflowSummary as WSummary } from "@/lib/types";

import { Card, CardBody, CardHeader, CardTitle } from "./ui/Card";
import { StatusBadge } from "./StatusBadge";

interface Props {
  workflowId: string;
  refresh?: number; // counter to force re-fetch
}

function formatINR(n: number): string {
  if (n >= 10_000_000) return `Rs ${(n / 10_000_000).toFixed(2)}Cr`;
  if (n >= 100_000) return `Rs ${(n / 100_000).toFixed(2)}L`;
  return `Rs ${n.toLocaleString("en-IN")}`;
}

export function WorkflowSummary({ workflowId, refresh = 0 }: Props) {
  const [data, setData] = useState<WSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    // Keep polling for any non-terminal status. Stop once it settles.
    const ACTIVE = new Set(["running", "applying", "destroying"]);
    const TERMINAL = new Set([
      "completed",
      "deployed",
      "destroyed",
      "errored",
      "awaiting_approval", // idle — UI controls next step
    ]);

    const tick = async () => {
      try {
        const s = await api.getWorkflow(workflowId);
        if (cancelled) return;
        setData(s);
        if (TERMINAL.has(s.status)) return;
        if (ACTIVE.has(s.status)) {
          timer = setTimeout(tick, 2000);
        }
      } catch {
        if (!cancelled) timer = setTimeout(tick, 3000);
      }
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [workflowId, refresh]);

  if (!data) {
    return (
      <Card>
        <CardBody>
          <div className="h-24 animate-pulse rounded bg-zinc-100" />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div>
          <CardTitle>{data.customer_name}</CardTitle>
          <p className="mt-0.5 font-mono text-xs text-zinc-500">
            {workflowId}
          </p>
        </div>
        <StatusBadge status={data.status} decision={data.final_decision} />
      </CardHeader>

      <CardBody>
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Metric
            icon={<MapPin className="h-4 w-4" />}
            label="Sites"
            value={String(data.site_count || "—")}
          />
          <Metric
            icon={<Coins className="h-4 w-4" />}
            label="Cost / month"
            value={
              data.estimated_cost_inr_monthly
                ? formatINR(data.estimated_cost_inr_monthly)
                : "—"
            }
          />
          <Metric
            icon={<Clock className="h-4 w-4" />}
            label="Duration"
            value={data.duration_sec ? `${data.duration_sec}s` : "running…"}
          />
          <Metric
            icon={<Calendar className="h-4 w-4" />}
            label="Started"
            value={new Date(data.started_at).toLocaleTimeString()}
          />
        </dl>

        {data.error && (
          <div className="mt-4 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            {data.error}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Metric({
  icon, label, value,
}: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-zinc-500">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-h3 font-semibold text-zinc-900">{value}</div>
    </div>
  );
}
