"use client";

import React from "react";

type ContextCopilotShellProps = {
  left: React.ReactNode;
  main: React.ReactNode;
  right: React.ReactNode;
  className?: string;
};

/** Shared three-column shell: context rail, workspace, copilot rail. */
export default function ContextCopilotShell({ left, main, right, className = "" }: ContextCopilotShellProps) {
  return (
    <div className={`grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)_320px] ${className}`}>
      <aside className="space-y-4">{left}</aside>
      <section className="min-w-0">{main}</section>
      <aside className="space-y-4">{right}</aside>
    </div>
  );
}
