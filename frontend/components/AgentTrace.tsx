"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { FullWorkflow, TraceResponse } from "@/lib/types";

import { AgentPipeline } from "./agents/AgentPipeline";
import { AgentTimeline } from "./agents/AgentTimeline";
import { parseTrace, pipelineStatus } from "./agents/parseTrace";

interface Props {
  workflowId: string;
  pollInterval?: number;
  onFinished?: () => void;
}

export function AgentTrace({
  workflowId,
  pollInterval = 1000,
  onFinished,
}: Props) {
  const [data, setData] = useState<TraceResponse | null>(null);
  const [full, setFull] = useState<FullWorkflow | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Track last seen status so /full is fetched ONCE per phase change,
  // not every poll tick. Likewise onFinished fires only on transition.
  const lastStatusRef = useRef<string | null>(null);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    // Truly terminal — stop polling. Note: "errored" is NOT here because the
    // user can still trigger a cleanup destroy from this state, which moves
    // status into "destroying" and we need to keep updating.
    const TERMINAL = new Set(["deployed", "destroyed"]);
    // settled phases — refresh /full once per transition
    const SETTLED = new Set([
      "awaiting_approval",
      "deployed",
      "destroyed",
      "errored",
      "completed",
    ]);

    const tick = async () => {
      try {
        const t = await api.getTrace(workflowId);
        if (cancelled) return;
        setData(t);

        const prev = lastStatusRef.current;
        const changed = prev !== t.status;
        if (changed) lastStatusRef.current = t.status;

        // Only fetch /full and fire onFinished on TRANSITION into a settled state.
        if (changed && SETTLED.has(t.status)) {
          try {
            const f = await api.getFull(workflowId);
            if (!cancelled) setFull(f);
          } catch {
            /* non-fatal */
          }
          onFinishedRef.current?.();
        }

        if (TERMINAL.has(t.status)) {
          return; // stop polling
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "Failed to fetch trace");
      }

      // While running/applying/destroying: fast poll. Idle (awaiting_approval): slow.
      const cur = lastStatusRef.current;
      const delay = cur === "awaiting_approval" ? 5000 : pollInterval;
      timer = setTimeout(tick, delay);
    };

    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [workflowId, pollInterval]);

  if (error) {
    return (
      <div className="rounded-md border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
        {error}
      </div>
    );
  }

  const events = parseTrace(data?.trace ?? []);
  const { done, active } = pipelineStatus(events);
  const isRunning = data ? !data.finished : true;

  const status = data?.status;
  const isApplying = status === "applying";
  const isDestroying = status === "destroying";
  const longPhase = isApplying || isDestroying;

  // Derive copy from the actual workflow size so the banner doesn't lie about
  // resource counts. Falls back to a generic message when site count is unknown.
  const siteCount = full?.intake?.site_count ?? 0;
  const vpnCount = siteCount; // 1 VPN per site
  const sitesLabel = siteCount === 1 ? "1 site" : `${siteCount} sites`;
  const typicalApply =
    siteCount <= 0 ? "a few minutes"
      : siteCount <= 2 ? "5-8 minutes"
      : siteCount <= 5 ? "8-12 minutes"
      : "15-25 minutes";
  const typicalDestroy = siteCount <= 2 ? "3-5 minutes" : "5-10 minutes";
  const applyMessage = siteCount > 0
    ? `terraform apply is creating ${siteCount + 1} VPCs (1 central + ${siteCount} site), a Transit Gateway, ${vpnCount} VPN connection${vpnCount === 1 ? "" : "s"}, ${siteCount} EC2 SD-WAN edge${siteCount === 1 ? "" : "s"}, and ${vpnCount * 2} IPsec tunnels. Typical duration: ${typicalApply} for ${sitesLabel}. Progress is appended below every 30 seconds.`
    : "terraform apply is creating VPCs, a Transit Gateway, VPN connections, EC2 SD-WAN edges, and IPsec tunnels. Progress is appended below every 30 seconds.";
  const destroyMessage = `terraform destroy is removing all AWS resources. Typical duration: ${typicalDestroy}.`;

  return (
    <div className="space-y-6">
      <AgentPipeline done={done} active={active} workflowStatus={status} />

      {/* Prominent banner when terraform apply / destroy is running */}
      {longPhase && (
        <div className="rounded-lg border-2 border-vi-red/40 bg-gradient-to-r from-vi-red/5 to-vi-yellow/5 p-4">
          <div className="flex items-start gap-3">
            <div className="relative flex h-10 w-10 shrink-0 items-center justify-center">
              <span className="absolute inset-0 animate-ping rounded-full bg-vi-red/30" />
              <span className="absolute inset-2 animate-pulse-dot rounded-full bg-vi-red" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-zinc-900">
                {isApplying
                  ? "Provisioning real AWS infrastructure…"
                  : "Destroying AWS infrastructure…"}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-zinc-600">
                {isApplying ? applyMessage : destroyMessage}
              </p>
              <p className="mt-2 text-[11px] text-zinc-500">
                Safe to leave this page — workflow continues in background. AWS billing has started.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          {isRunning ? (
            <>
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-vi-yellow" />
              <span className="font-medium text-zinc-700">
                {isApplying ? "Deploying" : isDestroying ? "Destroying" : "Agents working"}
              </span>
              <span className="text-zinc-400">
                · {done.size}/8 complete{active ? ` · ${active} running` : ""}
              </span>
            </>
          ) : (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              <span className="font-medium text-zinc-700">Workflow complete</span>
              {!full && (
                <span className="text-zinc-400">· loading details…</span>
              )}
            </>
          )}
        </div>
        <span className="text-zinc-400">{events.length} events</span>
      </div>

      <AgentTimeline events={events} isRunning={isRunning} full={full} />
    </div>
  );
}
