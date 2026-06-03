"use client";

import { FileDown } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/Button";

interface Props {
  workflowId: string;
  available: boolean;
}

export function PdfDownload({ workflowId, available }: Props) {
  if (!available) {
    return (
      <Button variant="secondary" disabled size="lg">
        <FileDown className="h-4 w-4" />
        Audit PDF (generating…)
      </Button>
    );
  }
  return (
    <a href={api.pdfUrl(workflowId)} target="_blank" rel="noreferrer">
      <Button size="lg">
        <FileDown className="h-4 w-4" />
        Download Audit PDF
      </Button>
    </a>
  );
}
