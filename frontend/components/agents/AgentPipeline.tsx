"use client";

import { Check } from "lucide-react";

import { AGENT_META, PIPELINE_ORDER, type AgentKey } from "./agentMeta";

interface Props {
  done: Set<AgentKey>;
  active: AgentKey | null;
  workflowStatus?: string;
}

/** Workflow status overrides the parser-derived active agent so the UI
 *  stays expressive during long phases (terraform apply, destroy). */
function deriveActive(parsed: AgentKey | null, status?: string): AgentKey | null {
  if (status === "applying" || status === "destroying") return "Deployment";
  return parsed;
}

export function AgentPipeline({ done, active, workflowStatus }: Props) {
  const effectiveActive = deriveActive(active, workflowStatus);
  return (
    <div className="overflow-x-auto pb-2">
      <ol className="flex min-w-[640px] items-stretch gap-1">
        {PIPELINE_ORDER.map((key, idx) => {
          const meta = AGENT_META[key];
          const isDone = done.has(key);
          const isActive = effectiveActive === key;
          const isPending = !isDone && !isActive;
          const Icon = meta.Icon;

          return (
            <li
              key={key}
              className="flex flex-1 items-center"
              aria-current={isActive ? "step" : undefined}
            >
              <div className="flex w-full flex-col items-center">
                <div className="flex w-full items-center">
                  <div className={`h-px flex-1 ${idx === 0 ? "opacity-0" : isDone || isActive ? "bg-vi-red" : "bg-zinc-200"}`} />

                  <div
                    className={[
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-1 transition",
                      isDone
                        ? "bg-vi-red text-white ring-vi-red"
                        : isActive
                        ? "bg-vi-yellow text-zinc-900 ring-vi-yellow shadow-card-hover"
                        : "bg-white text-zinc-400 ring-zinc-200",
                    ].join(" ")}
                  >
                    {isDone ? (
                      <Check className="h-5 w-5" strokeWidth={2.5} />
                    ) : (
                      <Icon className="h-5 w-5" strokeWidth={1.75} />
                    )}
                    {isActive && (
                      <span className="absolute -mt-12 -ml-1 h-10 w-10 animate-ping rounded-full bg-vi-yellow/30" />
                    )}
                  </div>

                  <div className={`h-px flex-1 ${idx === PIPELINE_ORDER.length - 1 ? "opacity-0" : isDone ? "bg-vi-red" : "bg-zinc-200"}`} />
                </div>

                <div className="mt-2 text-center">
                  <div
                    className={[
                      "text-xs font-medium leading-tight",
                      isDone || isActive ? "text-zinc-900" : "text-zinc-400",
                    ].join(" ")}
                  >
                    {meta.name}
                  </div>
                  <div
                    className={[
                      "mt-0.5 text-[10px] leading-tight",
                      isActive ? "text-vi-red" : "text-zinc-400",
                    ].join(" ")}
                  >
                    {isActive ? "running…" : isDone ? "complete" : meta.tagline}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
