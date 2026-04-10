import type { ReactNode } from "react";

/** Avoid stale cached HTML for this interactive route during development and deploys. */
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function HeatmapLayout({ children }: { children: ReactNode }) {
  return children;
}
