"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Sparkles } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "./ui/Button";

const EXAMPLES = [
  {
    label: "Hero - 10 BFSI retail sites",
    customer: "Bharat Manufacturing Ltd",
    request:
      "Onboard 10 retail stores: 5 in Maharashtra (Pune, Nashik, Aurangabad, Solapur, Kolhapur) and 5 in Karnataka (Mysore, Hubli, Mangalore, Belgaum, Davangere). 100 Mbps SD-WAN, BFSI tier, by month-end.",
  },
  {
    label: "2 cities · 2 states · BFSI",
    customer: "Rapid Retail India",
    request:
      "Onboard 2 retail stores: 1 in Maharashtra (Mumbai) and 1 in Karnataka (Bangalore). 200 Mbps SD-WAN, BFSI tier, by July 31.",
  },
  {
    label: "Small standard - 2 sites",
    customer: "TechStart Pvt Ltd",
    request:
      "Onboard 2 office sites in Pune and Mumbai with 50 Mbps SD-WAN each, standard tier.",
  },
  {
    label: "Out-of-coverage (will be rejected)",
    customer: "Adventure Resorts Pvt Ltd",
    request:
      "Onboard 3 sites in Leh, Srinagar, and Port Blair with 100 Mbps SD-WAN.",
  },
];

export function WorkflowForm() {
  const router = useRouter();
  const [customer, setCustomer] = useState("Bharat Manufacturing Ltd");
  const [request, setRequest] = useState(EXAMPLES[0].request);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (request.trim().length < 10) {
      setError("Please describe your request (at least 10 characters).");
      return;
    }
    setLoading(true);
    try {
      const res = await api.createWorkflow({
        user_request: request.trim(),
        customer_name: customer.trim() || "Unnamed Customer",
      });
      router.push(`/workflows/${res.workflow_id}`);
    } catch (e: any) {
      setError(e?.message || "Failed to start workflow");
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-700">
          Customer account
          <span className="ml-2 text-xs font-normal text-zinc-500">
            Billing entity name
          </span>
        </label>
        <input
          value={customer}
          onChange={(e) => setCustomer(e.target.value)}
          className="block w-full rounded-md border border-zinc-300 bg-white px-3.5 py-2.5 text-sm shadow-sm placeholder:text-zinc-400 focus:border-vi-red focus:outline-none focus:ring-2 focus:ring-vi-red/20"
          placeholder="e.g., Bharat Manufacturing Ltd"
        />
      </div>

      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-700">
          Service request
          <span className="ml-2 text-xs font-normal text-zinc-500">
            Natural-language intent
          </span>
        </label>
        <textarea
          value={request}
          onChange={(e) => setRequest(e.target.value)}
          rows={6}
          className="block w-full resize-y rounded-md border border-zinc-300 bg-white px-3.5 py-2.5 text-sm shadow-sm placeholder:text-zinc-400 focus:border-vi-red focus:outline-none focus:ring-2 focus:ring-vi-red/20"
          placeholder="Onboard 10 retail stores across Maharashtra and Karnataka with SD-WAN to AWS Mumbai, 100 Mbps each, ISO 27001 compliance."
        />
        <p className="mt-1.5 text-[11px] text-zinc-400">
          Sites, bandwidth, compliance tier, and priority apps are extracted automatically.
        </p>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          Try an example
        </p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => {
                setCustomer(ex.customer);
                setRequest(ex.request);
              }}
              className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:border-vi-red hover:text-vi-red"
              type="button"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 border-t border-zinc-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-zinc-500 sm:max-w-[55%]">
          Supervisor Agent routes through 8 specialists in ~60 seconds.
        </p>
        <Button
          onClick={submit}
          disabled={loading}
          size="lg"
          className="shrink-0 whitespace-nowrap"
        >
          <Sparkles className="h-4 w-4" />
          {loading ? "Starting…" : "Run Workflow"}
        </Button>
      </div>
    </div>
  );
}
