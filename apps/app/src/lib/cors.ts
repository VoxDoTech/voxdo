/**
 * CORS for the Capacitor mobile app (apps/mobile).
 *
 * The app runs in a WebView on `https://localhost` (Android) /
 * `capacitor://localhost` (iOS) and talks to this API cross-origin with a
 * bearer token instead of cookies. Origins are allow-listed — never `*` —
 * so credentialed browser requests stay same-origin only.
 */

const ALLOWED_ORIGIN_PATTERNS = [
  /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/,
  /^capacitor:\/\/localhost$/,
];

function allowedOrigin(request: Request): string | null {
  const origin = request.headers.get("origin");
  if (!origin) return null;
  return ALLOWED_ORIGIN_PATTERNS.some((p) => p.test(origin)) ? origin : null;
}

function corsHeaders(request: Request): Record<string, string> {
  const origin = allowedOrigin(request);
  if (!origin) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers":
      "content-type, authorization, x-requested-with",
    // Better Auth's bearer plugin returns the token in this header.
    "Access-Control-Expose-Headers": "set-auth-token",
    Vary: "Origin",
  };
}

export function withCors(request: Request, response: Response): Response {
  const headers = corsHeaders(request);
  if (Object.keys(headers).length === 0) return response;
  const merged = new Headers(response.headers);
  for (const [key, value] of Object.entries(headers)) {
    merged.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: merged,
  });
}

export function handleCorsPreflight(request: Request): Response | null {
  if (request.method !== "OPTIONS") return null;
  return new Response(null, { status: 204, headers: corsHeaders(request) });
}
