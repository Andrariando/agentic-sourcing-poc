/**
 * User-facing priority labels (High / Medium / Low / Lowest). Stored tier codes stay on the server.
 */
export function heatmapTierLabel(tier: string | null | undefined): string {
  switch (tier) {
    case "T1":
      return "High";
    case "T2":
      return "Medium";
    case "T3":
      return "Low";
    case "T4":
      return "Lowest";
    default:
      return (tier as string) || "—";
  }
}
