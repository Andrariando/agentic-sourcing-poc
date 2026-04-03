"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function navCls(active: boolean): string {
  if (active) {
    return "flex items-center px-3 py-2 text-sm font-medium rounded-md bg-slate-800 text-white border border-slate-700";
  }
  return "flex items-center px-3 py-2 text-sm font-medium rounded-md hover:bg-slate-800 hover:text-white transition-colors";
}

export default function SidebarNav() {
  const pathname = usePathname();
  const onHeatmap = pathname === "/heatmap";
  const onHeatmapMatrix = pathname === "/heatmap/matrix";
  const onIntake = pathname === "/intake";
  const onCases = pathname === "/cases";
  const onS2cPerformance = pathname === "/s2c/performance";

  return (
    <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-8 mt-2">
      <div>
        <h2 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Opportunity Prioritization
        </h2>
        <div className="space-y-1">
          <Link href="/heatmap" className={navCls(onHeatmap)}>
            Sourcing Priority List
          </Link>
          <Link href="/heatmap/matrix" className={navCls(onHeatmapMatrix)}>
            Performance Dashboard
          </Link>
          <Link href="/intake" className={navCls(onIntake)}>
            Sourcing Intake Form (New Request)
          </Link>
        </div>
      </div>

      <div>
        <h2 className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Source-to-Contract (S2C) Execution
        </h2>
        <div className="space-y-1">
          <Link href="/cases" className={navCls(onCases)}>
            S2C Case Dashboard
          </Link>
          <Link href="/s2c/performance" className={navCls(onS2cPerformance)}>
            S2C Performance Dashboard
          </Link>
        </div>
      </div>
    </nav>
  );
}
