import { Badge } from "./ui/Badge";
import type { WorkflowSummary } from "@/lib/types";

interface Props {
  status: WorkflowSummary["status"];
  decision?: WorkflowSummary["final_decision"];
}

export function StatusBadge({ status, decision }: Props) {
  if (status === "running")
    return (
      <Badge tone="info">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-info" />
        Running
      </Badge>
    );

  if (status === "awaiting_approval")
    return (
      <Badge tone="warning">
        <span className="h-1.5 w-1.5 rounded-full bg-warning" />
        Awaiting approval
      </Badge>
    );

  if (status === "applying")
    return (
      <Badge tone="brand">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-vi-red" />
        Deploying
      </Badge>
    );

  if (status === "destroying")
    return (
      <Badge tone="warning">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-warning" />
        Destroying
      </Badge>
    );

  if (status === "deployed") return <Badge tone="success">Deployed</Badge>;
  if (status === "destroyed") return <Badge tone="neutral">Destroyed</Badge>;
  if (status === "errored") return <Badge tone="danger">Error</Badge>;

  if (decision === "rejected") return <Badge tone="danger">Rejected</Badge>;
  if (decision === "clarification_needed")
    return <Badge tone="warning">Needs clarification</Badge>;
  if (decision === "approved_with_escalation")
    return <Badge tone="warning">Approved (escalation)</Badge>;
  if (decision === "approved_auto") return <Badge tone="success">Approved</Badge>;
  return <Badge tone="neutral">Completed</Badge>;
}
