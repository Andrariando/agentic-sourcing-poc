/** Base URL baked in at build time (NEXT_PUBLIC_*). No trailing slash. */
export function getApiBaseUrl(): string {
  const v = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (v) return v.replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    // Dev fallback: when app is opened via LAN IP (not localhost), do not point API to localhost.
    return `${protocol}//${hostname}:8000`;
  }
  return "http://localhost:8000";
}

/**
 * Extra context when fetches fail (esp. Vercel HTTPS + missing env → localhost mixed content).
 */
export function apiConnectivityHint(): string {
  if (typeof window === "undefined") return "";
  const hasEnv = Boolean(process.env.NEXT_PUBLIC_API_URL?.trim());
  if (window.location.protocol === "https:" && !hasEnv) {
    return " This deployment was built without NEXT_PUBLIC_API_URL, so the app uses http://localhost:8000 — browsers block that from HTTPS. In Vercel → Settings → Environment Variables, set NEXT_PUBLIC_API_URL to your ngrok HTTPS origin for Preview and Production, then Redeploy.";
  }
  if (!hasEnv) {
    return " NEXT_PUBLIC_API_URL was not set at build time; fallback uses current host on port 8000.";
  }
  return " Keep uvicorn and ngrok running on your PC. If ngrok restarted, copy the new HTTPS URL into Vercel and redeploy.";
}
