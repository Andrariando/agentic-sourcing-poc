"use client";

import React from "react";
import { MessageSquare } from "lucide-react";
import { PROCURABOT_BRAND } from "@/lib/procurabot-brand";

type ProcuraBotIdentityProps = {
  subtitle?: string;
  compact?: boolean;
  className?: string;
};

export default function ProcuraBotIdentity({ subtitle, compact = false, className = "" }: ProcuraBotIdentityProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`.trim()}>
      <div className="w-8 h-8 rounded-lg bg-sponsor-blue flex items-center justify-center shadow-md shrink-0">
        <MessageSquare className="w-4 h-4 text-white" />
      </div>
      <div className="min-w-0">
        <h2 className={`${compact ? "text-base" : "text-lg"} font-bold text-slate-900 leading-tight`}>
          {PROCURABOT_BRAND.name}
        </h2>
        <p className="text-xs text-slate-500 font-medium truncate">
          {subtitle || `${PROCURABOT_BRAND.statusReady} · ${PROCURABOT_BRAND.roleLabel}`}
        </p>
      </div>
    </div>
  );
}
