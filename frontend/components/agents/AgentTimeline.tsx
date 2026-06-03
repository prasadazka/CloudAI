"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, ChevronDown, ChevronRight, Play } from "lucide-react";

import type { FullWorkflow } from "@/lib/types";

import { AGENT_META, type AgentKey } from "./agentMeta";
import { AgentDetails } from "./AgentDetails";
import type { ParsedEvent } from "./parseTrace";

interface Props {
  events: ParsedEvent[];
  isRunning: boolean;
  full: FullWorkflow | null;
}

const DETAIL_AGENTS: AgentKey[] = [
  "Intake",
  "Discovery",
  "Policy",
  "Architecture",
  "IaC",
  "Deployment",
  "Validation",
  "Audit",
];

export function AgentTimeline({ events, isRunning, full }: Props) {
  const endRef = useRef<HTMLLIElement>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  function toggle(i: number) {
    setExpanded((e) => ({ ...e, [i]: !e[i] }));
  }

  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute left-5 top-2 bottom-2 w-px bg-gradient-to-b from-zinc-200 via-zinc-200 to-transparent"
      />

      <ol className="relative max-h-[40rem] space-y-3 overflow-y-auto pr-1">
        {events.length === 0 && (
          <li className="ml-12 text-sm text-zinc-500">
            Waiting for first agent…
          </li>
        )}

        {events.map((ev, i) => (
          <TimelineRow
            key={i}
            ev={ev}
            isLast={i === events.length - 1}
            isRunning={isRunning}
            expanded={!!expanded[i]}
            onToggle={() => toggle(i)}
            full={full}
          />
        ))}

        <li ref={endRef} aria-hidden />
      </ol>
    </div>
  );
}

function TimelineRow({
  ev,
  isLast,
  isRunning,
  expanded,
  onToggle,
  full,
}: {
  ev: ParsedEvent;
  isLast: boolean;
  isRunning: boolean;
  expanded: boolean;
  onToggle: () => void;
  full: FullWorkflow | null;
}) {
  if (ev.kind === "start") {
    return (
      <li className="animate-slide-in flex items-center gap-3 pl-1">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-vi-yellow/20 text-vi-red ring-1 ring-vi-yellow/40">
          <Play className="h-4 w-4 fill-vi-red" strokeWidth={0} />
        </div>
        <div className="flex-1 text-sm text-zinc-700">{ev.message}</div>
      </li>
    );
  }

  if (ev.kind === "routing") {
    const target = ev.routingTo;
    const TargetIcon = target ? AGENT_META[target].Icon : ArrowRight;
    return (
      <li className="animate-slide-in flex items-center gap-3 pl-1">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100 text-zinc-400 ring-1 ring-zinc-200">
          <ArrowRight className="h-4 w-4" />
        </div>
        <div className="flex flex-1 items-center gap-2 text-xs text-zinc-500">
          <span className="font-medium text-zinc-700">Supervisor</span>
          <span>routes to</span>
          <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-900">
            <TargetIcon className="h-3 w-3" strokeWidth={2} />
            {target ?? "?"}
          </span>
          {isLast && isRunning && (
            <span className="ml-2 inline-flex items-center gap-1.5 text-vi-red">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-vi-red" />
              thinking
            </span>
          )}
          {ev.timestamp && (
            <span className="ml-auto font-mono text-[10px] text-zinc-400">
              {ev.timestamp}
            </span>
          )}
        </div>
      </li>
    );
  }

  const agent = ev.agent as AgentKey | undefined;
  const meta = agent ? AGENT_META[agent] : null;
  const Icon = meta?.Icon ?? ArrowRight;
  const isError = ev.kind === "error";
  const isClarify = ev.kind === "clarification";
  const canExpand = agent && DETAIL_AGENTS.includes(agent);
  const detailReady = canExpand && full !== null;

  return (
    <li className="animate-slide-in flex gap-3 pl-1">
      <div
        className={[
          "z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-1",
          isError
            ? "bg-danger-soft text-danger ring-red-200"
            : isClarify
            ? "bg-warning-soft text-warning ring-amber-200"
            : "bg-white text-vi-red ring-vi-red/30 shadow-card",
        ].join(" ")}
      >
        <Icon className="h-4 w-4" strokeWidth={2} />
      </div>

      <div className="min-w-0 flex-1 rounded-lg border border-zinc-200 bg-white p-3 shadow-card">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-zinc-900">
            {meta?.name ?? "Event"}
          </span>
          {meta && (
            <span className="text-xs text-zinc-400">· {meta.tagline}</span>
          )}
          {ev.timestamp && (
            <span className="ml-auto font-mono text-[10px] text-zinc-400">
              {ev.timestamp}
            </span>
          )}
        </div>

        <p className="mt-1 text-sm leading-relaxed text-zinc-700">
          {ev.message}
        </p>

        {ev.metrics.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ev.metrics.slice(0, 6).map((m, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 rounded-md bg-zinc-50 px-2 py-0.5 text-[11px] ring-1 ring-zinc-200"
              >
                <span className="text-zinc-500">{m.label}</span>
                <span className="font-medium text-zinc-900">{m.value}</span>
              </span>
            ))}
          </div>
        )}

        {canExpand && (
          <>
            <button
              type="button"
              onClick={onToggle}
              disabled={!detailReady}
              className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-vi-red hover:underline disabled:text-zinc-400 disabled:no-underline"
            >
              {expanded ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
              {detailReady
                ? expanded
                  ? "Hide details"
                  : "View details"
                : "Details available when workflow completes"}
            </button>

            {expanded && agent && (
              <div className="mt-3 border-t border-zinc-200 pt-3">
                <AgentDetails agent={agent} full={full} />
              </div>
            )}
          </>
        )}
      </div>
    </li>
  );
}
