"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { AgentTrace } from "@/components/AgentTrace";
import { ApprovalGate } from "@/components/ApprovalGate";
import { PdfDownload } from "@/components/PdfDownload";
import { WorkflowSummary } from "@/components/WorkflowSummary";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { FullWorkflow, WorkflowSummary as WS } from "@/lib/types";

export default function WorkflowDetail({
  params,
}: {
  params: { id: string };
}) {
  const [summary, setSummary] = useState<WS | null>(null);
  const [full, setFull] = useState<FullWorkflow | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const s = await api.getWorkflow(params.id);
        if (!cancelled) setSummary(s);
        // Once iac exists (after plan), fetch full for the approval card.
        if (s.status !== "running") {
          try {
            const f = await api.getFull(params.id);
            if (!cancelled) setFull(f);
          } catch {
            /* not fatal */
          }
        }
      } catch {
        /* */
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [params.id, refresh]);

  return (
    <div className="space-y-5 sm:space-y-6">
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-vi-red"
        >
          <ArrowLeft className="h-4 w-4" />
          New request
        </Link>
      </div>

      <WorkflowSummary workflowId={params.id} refresh={refresh} />

      <ApprovalGate
        workflowId={params.id}
        summary={summary}
        full={full}
        onApproved={() => setRefresh((r) => r + 1)}
      />

      {/* 12-col grid for better space distribution */}
      <div className="grid grid-cols-1 gap-5 sm:gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-8 xl:col-span-9">
          <CardHeader>
            <CardTitle>Live agent activity</CardTitle>
            <p className="mt-1 text-sm text-zinc-500">
              Each event is a real decision from one of the 8 agents.
            </p>
          </CardHeader>
          <CardBody className="p-4 sm:p-5">
            <AgentTrace
              workflowId={params.id}
              onFinished={() => setRefresh((r) => r + 1)}
            />
          </CardBody>
        </Card>

        <Card className="self-start lg:col-span-4 xl:col-span-3 lg:sticky lg:top-24">
          <CardHeader>
            <CardTitle>Deliverable</CardTitle>
          </CardHeader>
          <CardBody className="space-y-4 p-4 sm:p-5">
            <p className="text-sm leading-relaxed text-zinc-600">
              The Cloud Siddhi compliance PDF is produced by the Audit Agent
              <em> after deployment</em>. It documents the real infrastructure
              state, validation results, and approval chain.
            </p>
            <PdfDownload
              workflowId={params.id}
              available={!!summary?.audit_pdf_available}
            />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
