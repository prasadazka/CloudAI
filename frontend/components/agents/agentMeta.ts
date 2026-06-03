import {
  Brain,
  Cloud,
  FileCheck,
  Mic,
  Network,
  Rocket,
  Search,
  ShieldCheck,
  TerminalSquare,
  type LucideIcon,
} from "lucide-react";

export type AgentKey =
  | "Supervisor"
  | "Intake"
  | "Discovery"
  | "Policy"
  | "Architecture"
  | "IaC"
  | "Deployment"
  | "Validation"
  | "Audit";

export interface AgentMeta {
  key: AgentKey;
  name: string;
  tagline: string;
  Icon: LucideIcon;
}

export const AGENT_META: Record<AgentKey, AgentMeta> = {
  Supervisor:   { key: "Supervisor",   name: "Supervisor",   tagline: "Orchestrator",         Icon: Brain },
  Intake:       { key: "Intake",       name: "Intake",       tagline: "Understands request",  Icon: Mic },
  Discovery:    { key: "Discovery",    name: "Discovery",    tagline: "Looks up customer",    Icon: Search },
  Policy:       { key: "Policy",       name: "Policy",       tagline: "Governance gate",      Icon: ShieldCheck },
  Architecture: { key: "Architecture", name: "Architecture", tagline: "Designs solution",     Icon: Network },
  IaC:          { key: "IaC",          name: "IaC",          tagline: "Generates Terraform",  Icon: TerminalSquare },
  Deployment:   { key: "Deployment",   name: "Deployment",   tagline: "Applies plan",         Icon: Rocket },
  Validation:   { key: "Validation",   name: "Validation",   tagline: "Tests tunnels",        Icon: Cloud },
  Audit:        { key: "Audit",        name: "Audit",        tagline: "Compliance PDF",       Icon: FileCheck },
};

export const PIPELINE_ORDER: AgentKey[] = [
  "Intake",
  "Discovery",
  "Policy",
  "Architecture",
  "IaC",
  "Deployment",
  "Validation",
  "Audit",
];
