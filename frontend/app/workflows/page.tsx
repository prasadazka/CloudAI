"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { WorkflowSummary } from "@/lib/types";

export default function WorkflowsList() {
  const [data, setData] = useState<WorkflowSummary[] | null>(null);

  useEffect(() => {
    api.listWorkflows(50).then(setData).catch(() => setData([]));
    const t = setInterval(() => {
      api.listWorkflows(50).then(setData).catch(() => null);
    }, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h1 className="text-h1 font-bold text-zinc-900">Recent workflows</h1>
      <p className="mt-2 mb-8 text-zinc-600">
        Most recent requests across all customers.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>
            {data ? `${data.length} workflow${data.length === 1 ? "" : "s"}` : "Loading…"}
          </CardTitle>
        </CardHeader>
        <CardBody className="p-0">
          {data === null && (
            <div className="px-5 py-10 text-center text-sm text-zinc-500">Loading…</div>
          )}
          {data?.length === 0 && (
            <div className="px-5 py-10 text-center text-sm text-zinc-500">
              No workflows yet.{" "}
              <Link href="/" className="text-vi-red hover:underline">
                Start one
              </Link>
              .
            </div>
          )}
          {data && data.length > 0 && (
            <ul className="divide-y divide-zinc-200">
              {data.map((w) => (
                <li key={w.workflow_id}>
                  <Link
                    href={`/workflows/${w.workflow_id}`}
                    className="flex items-center justify-between gap-4 px-5 py-3 transition hover:bg-zinc-50"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="font-medium text-zinc-900">{w.customer_name}</span>
                        <StatusBadge status={w.status} decision={w.final_decision} />
                      </div>
                      <div className="mt-0.5 flex items-center gap-4 font-mono text-xs text-zinc-500">
                        <span>{w.workflow_id}</span>
                        <span>{w.site_count} sites</span>
                        {w.duration_sec && <span>{w.duration_sec}s</span>}
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-400" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
