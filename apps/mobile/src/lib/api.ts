import type { AppRouter } from "@acme/api";
import { Preferences } from "@capacitor/preferences";
import { createORPCClient } from "@orpc/client";
import { RPCLink } from "@orpc/client/fetch";
import type { RouterClient } from "@orpc/server";
import { z } from "zod";

/**
 * Backend base URL. Set VITE_API_URL in apps/mobile/.env — on the Android
 * emulator use http://10.0.2.2:3000 (localhost inside the emulator is the
 * emulator itself), on a physical device use the dev machine's LAN IP.
 */
const envUrl = import.meta.env.VITE_API_URL as string | undefined;

// Production builds must talk HTTPS — a cleartext endpoint would expose
// the bearer token to network observers.
if (import.meta.env.PROD && envUrl?.startsWith("http://")) {
  throw new Error(
    "VITE_API_URL must use https:// in production builds (http is dev-only)",
  );
}

export const API_URL =
  envUrl ?? (import.meta.env.DEV ? "http://localhost:3000" : "");

const TOKEN_KEY = "voxdo.auth_token";

async function getAuthToken(): Promise<string | null> {
  const { value } = await Preferences.get({ key: TOKEN_KEY });
  return value;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const api: RouterClient<AppRouter> = createORPCClient(
  new RPCLink({
    origin: API_URL,
    url: "/api/orpc",
    headers: authHeaders,
  }),
);

export interface SessionUser {
  id: string;
  email: string;
  name: string;
}

const sessionUserSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
});
const sessionResponseSchema = z
  .object({ user: sessionUserSchema.nullish() })
  .nullable();
const authErrorSchema = z
  .object({ message: z.string().optional(), code: z.string().optional() })
  .nullable();

/** Returns the signed-in user or null. */
export async function fetchSession(): Promise<SessionUser | null> {
  const res = await fetch(`${API_URL}/api/auth/get-session`, {
    headers: await authHeaders(),
  });
  if (!res.ok) return null;
  const parsed = sessionResponseSchema.safeParse(
    await res.json().catch(() => null),
  );
  if (!parsed.success) return null;
  return parsed.data?.user ?? null;
}

async function authRequest(
  path: string,
  body: Record<string, unknown>,
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch(`${API_URL}/api/auth/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  // The bearer plugin returns the token in this response header.
  const token = res.headers.get("set-auth-token");
  if (token) {
    await Preferences.set({ key: TOKEN_KEY, value: token });
  }
  if (!res.ok) {
    const parsed = authErrorSchema.safeParse(
      await res.json().catch(() => null),
    );
    return {
      ok: false,
      error: parsed.success
        ? (parsed.data?.message ?? `HTTP ${res.status}`)
        : `HTTP ${res.status}`,
    };
  }
  return { ok: true };
}

export function signIn(email: string, password: string) {
  return authRequest("sign-in/email", { email, password });
}

export function signUp(email: string, password: string, name: string) {
  return authRequest("sign-up/email", { email, password, name });
}

export async function signOut(): Promise<void> {
  await fetch(`${API_URL}/api/auth/sign-out`, {
    method: "POST",
    headers: { ...(await authHeaders()) },
  }).catch(() => undefined);
  await Preferences.remove({ key: TOKEN_KEY });
}
