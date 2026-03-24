/**
 * Ngrok free tier returns an HTML interstitial for browser-like requests unless
 * this header is set. Harmless for non-ngrok backends.
 * @see https://ngrok.com/docs/troubleshooting/errors/err_ngrok_8012
 */
const NGROK_SKIP_BROWSER_WARNING = "ngrok-skip-browser-warning";

export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set(NGROK_SKIP_BROWSER_WARNING, "true");
  return fetch(input, { ...init, headers });
}
