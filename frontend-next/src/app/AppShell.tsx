"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import SidebarNav from "./SidebarNav";

type AppShellProps = {
  children: React.ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("procura_sidebar_collapsed");
      if (raw === "1") setSidebarCollapsed(true);
    } catch {
      // no-op for SSR/private mode edge cases
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("procura_sidebar_collapsed", sidebarCollapsed ? "1" : "0");
    } catch {
      // no-op for private mode edge cases
    }
  }, [sidebarCollapsed]);

  return (
    <div className="antialiased flex h-screen overflow-hidden bg-canvas text-ink font-sans">
      <aside
        className={`bg-slate-900/95 backdrop-blur-md text-slate-300 flex flex-col shadow-2xl z-20 shrink-0 border-r border-white/5 transition-[width] duration-200 ${
          sidebarCollapsed ? "w-16" : "w-64"
        }`}
      >
        <div className="h-16 flex items-center px-3 border-b border-white/10 shrink-0 justify-between gap-2">
          {!sidebarCollapsed ? (
            <Link href="/" className="font-bold text-base text-white tracking-wide leading-tight mt-2 font-syne hover:opacity-90 transition">
              <span className="text-mit-red block text-[10px] uppercase tracking-widest mb-0.5 font-bold">Procurement</span>
              Agentic System
            </Link>
          ) : (
            <Link href="/" className="w-10 h-10 rounded-md bg-slate-800 flex items-center justify-center text-white text-xs font-bold hover:bg-slate-700">
              AS
            </Link>
          )}

          <button
            type="button"
            onClick={() => setSidebarCollapsed((v) => !v)}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700"
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </button>
        </div>

        <SidebarNav collapsed={sidebarCollapsed} />

        <div className="p-4 border-t border-white/10 shrink-0">
          <div className={`flex items-center ${sidebarCollapsed ? "justify-center" : "gap-3"}`}>
            <div className="w-8 h-8 rounded-full bg-sponsor-blue flex items-center justify-center text-white font-bold text-xs">
              DR
            </div>
            {!sidebarCollapsed ? (
              <div>
                <p className="text-sm font-medium text-white">Sourcing Mgr</p>
                <p className="text-xs text-slate-400">IT Infrastructure</p>
              </div>
            ) : null}
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 bg-background overflow-y-auto">{children}</main>
    </div>
  );
}

