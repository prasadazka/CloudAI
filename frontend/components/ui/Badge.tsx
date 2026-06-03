import { HTMLAttributes } from "react";

type Tone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

const tones: Record<Tone, string> = {
  neutral: "bg-zinc-100 text-zinc-700 ring-zinc-200",
  success: "bg-success-soft text-success ring-green-200",
  warning: "bg-warning-soft text-warning ring-amber-200",
  danger:  "bg-danger-soft text-danger ring-red-200",
  info:    "bg-info-soft text-info ring-blue-200",
  brand:   "bg-vi-red/10 text-vi-red ring-vi-red/20",
};

export function Badge({ tone = "neutral", className = "", ...rest }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${tones[tone]} ${className}`}
      {...rest}
    />
  );
}
