"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  ListChecks,
  BarChart3,
  ClipboardPenLine,
  Upload,
  BriefcaseBusiness,
  Gauge,
} from "lucide-react";

function navCls(active: boolean): string {
  if (active) {
    return "flex items-center px-3 py-2 text-sm font-medium rounded-md bg-slate-800 text-white border border-slate-700";
  }
  return "flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 hover:text-white transition-colors";
}

type SidebarNavProps = {
  collapsed?: boolean;
};

export default function SidebarNav({ collapsed = false }: SidebarNavProps) {
  const pathname = usePathname();
  const onWelcome = pathname === "/welcome";
  const onHeatmap = pathname === "/heatmap";
  const onHeatmapMatrix = pathname === "/heatmap/matrix";
  const onIntake = pathname === "/intake";
  const onSystem1Upload = pathname === "/system-1/upload";
  const onCases = pathname === "/cases";
  const onS2cPerformance = pathname === "/s2c/performance";

  return (
    <nav className={`flex-1 overflow-y-auto py-6 px-3 mt-2 ${collapsed ? "space-y-6" : "space-y-8"}`}>
      <div>
        {!collapsed ? (
          <h2 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Executive
          </h2>
        ) : null}
        <div className="space-y-1">
          <Link href="/welcome" className={navCls(onWelcome)} title="Welcome">
            {collapsed ? <Home className="w-4 h-4 mx-auto" /> : "Welcome"}
          </Link>
        </div>
      </div>

      <div>
        {!collapsed ? (
          <h2 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Opportunity Prioritization
          </h2>
        ) : null}
        <div className="space-y-1">
          <Link href="/heatmap" className={navCls(onHeatmap)} title="Sourcing Priority List">
            {collapsed ? <ListChecks className="w-4 h-4 mx-auto" /> : "Sourcing Priority List"}
          </Link>
          <Link href="/heatmap/matrix" className={navCls(onHeatmapMatrix)} title="Performance Dashboard">
            {collapsed ? <BarChart3 className="w-4 h-4 mx-auto" /> : "Performance Dashboard"}
          </Link>
          <Link href="/intake" className={navCls(onIntake)} title="Sourcing Intake Form (New Request)">
            {collapsed ? <ClipboardPenLine className="w-4 h-4 mx-auto" /> : "Sourcing Intake Form (New Request)"}
          </Link>
          <Link href="/system-1/upload" className={navCls(onSystem1Upload)} title="Bulk File Upload">
            {collapsed ? <Upload className="w-4 h-4 mx-auto" /> : "Bulk File Upload"}
          </Link>
        </div>
      </div>

      <div>
        {!collapsed ? (
          <h2 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Source-to-Contract (S2C) Execution
          </h2>
        ) : null}
        <div className="space-y-1">
          <Link href="/cases" className={navCls(onCases)} title="S2C Case Dashboard">
            {collapsed ? <BriefcaseBusiness className="w-4 h-4 mx-auto" /> : "S2C Case Dashboard"}
          </Link>
          <Link href="/s2c/performance" className={navCls(onS2cPerformance)} title="S2C Performance Dashboard">
            {collapsed ? <Gauge className="w-4 h-4 mx-auto" /> : "S2C Performance Dashboard"}
          </Link>
        </div>
      </div>
    </nav>
  );
}
