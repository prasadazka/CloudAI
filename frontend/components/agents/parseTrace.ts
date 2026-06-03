import type { AgentKey } from "./agentMeta";

export type EventType = "start" | "routing" | "action" | "clarification" | "error";

export interface ParsedEvent {
  kind: EventType;
  timestamp?: string;       // "09:41:35"
  agent?: AgentKey;         // which agent owns this event
  routingTo?: AgentKey;     // for routing events
  rawMessage: string;
  message: string;          // human text after the agent name
  metrics: { label: string; value: string }[];
}

const KNOWN_AGENTS: AgentKey[] = [
  "Supervisor",
  "Intake",
  "Discovery",
  "Policy",
  "Architecture",
  "IaC",
  "Deployment",
  "Validation",
  "Audit",
];

const TS_RE = /^\[(\d{2}:\d{2}:\d{2})\]/;
const ROUTING_RE = /routing to (\w+) Agent/i;
const START_RE = /^\[start\]/;

function extractMetrics(msg: string): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = [];

  // key=value pairs (e.g., confidence=0.95, cost=Rs 16.25L/month)
  const kv = /(\w[\w_]*)=([^,;]+?)(?=,|\s{2,}|$)/g;
  let m: RegExpExecArray | null;
  while ((m = kv.exec(msg)) !== null) {
    out.push({ label: m[1], value: m[2].trim() });
  }

  // "N sites extracted", "N existing resources", "N recommendations", "N files generated"
  const counts = /(\d+)\s+(sites?(?:\s+\w+)?|existing resources|recommendations|files generated)/gi;
  while ((m = counts.exec(msg)) !== null) {
    out.push({ label: m[2], value: m[1] });
  }

  // "savings=Rs 0.68L/month" already caught by kv pattern.
  // "Rs X.XL/month" stand-alone
  const rs = /Rs\s+[\d.,]+L\/month/g;
  while ((m = rs.exec(msg)) !== null) {
    if (!out.some((o) => o.value.includes(m![0]))) {
      out.push({ label: "cost", value: m[0] });
    }
  }

  return out;
}

export function parseLine(line: string): ParsedEvent {
  if (START_RE.test(line)) {
    return {
      kind: "start",
      rawMessage: line,
      message: line.replace(/^\[start\]\s*/, ""),
      metrics: [],
    };
  }

  const tsMatch = line.match(TS_RE);
  const timestamp = tsMatch?.[1];
  const afterTs = tsMatch ? line.slice(tsMatch[0].length).trim() : line;

  // routing event
  const routing = afterTs.match(ROUTING_RE);
  if (routing) {
    return {
      kind: "routing",
      timestamp,
      agent: "Supervisor",
      routingTo: routing[1] as AgentKey,
      rawMessage: line,
      message: afterTs,
      metrics: [],
    };
  }

  // agent action: "AgentName: message body..."
  const agentMatch = afterTs.match(/^(\w+):\s*(.*)/);
  if (agentMatch && (KNOWN_AGENTS as string[]).includes(agentMatch[1])) {
    const agent = agentMatch[1] as AgentKey;
    const body = agentMatch[2];
    const lower = body.toLowerCase();
    // Only flag as error when supervisor logs the explicit "ERROR" marker.
    // Substrings like "0 failed" or status names like "validation_failed" are
    // legitimate agent output, not error events.
    const isExplicitError =
      body.includes("ERROR:") || /\b(plan|apply|destroy|validation)_failed\b/.test(body);
    const kind: EventType = isExplicitError
      ? "error"
      : agent === "Intake" && lower.includes("clarification=yes")
      ? "clarification"
      : "action";

    return {
      kind,
      timestamp,
      agent,
      rawMessage: line,
      message: body,
      metrics: extractMetrics(body),
    };
  }

  return {
    kind: "action",
    timestamp,
    rawMessage: line,
    message: afterTs,
    metrics: [],
  };
}

export function parseTrace(lines: string[]): ParsedEvent[] {
  return lines.map(parseLine);
}

/**
 * Returns the set of agents that have completed an action,
 * plus the currently-active agent (last routing destination not yet acted).
 */
export function pipelineStatus(events: ParsedEvent[]): {
  done: Set<AgentKey>;
  active: AgentKey | null;
} {
  const done = new Set<AgentKey>();
  let active: AgentKey | null = null;

  for (const ev of events) {
    if (ev.kind === "routing" && ev.routingTo) {
      active = ev.routingTo;
    } else if (
      (ev.kind === "action" ||
        ev.kind === "error" ||
        ev.kind === "clarification") &&
      ev.agent &&
      ev.agent !== "Supervisor"
    ) {
      // Any concrete agent emission means the agent has finished its turn,
      // even if the result was an error or a clarification request.
      done.add(ev.agent);
      if (active === ev.agent) active = null;
    }
  }

  return { done, active };
}
