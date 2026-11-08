import "server-only";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export type BackendResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: string };

/**
 * Server-to-server call to the Python API with the signed-in user's access token.
 * The token never reaches the browser. The backend verifies it itself (signature, issuer, expiry)
 * and makes every authorization decision from its own database.
 */
export async function backendFetch<T>(
  path: string,
  init: { method?: "GET" | "POST" | "PATCH"; body?: unknown; accessToken?: string } = {},
): Promise<BackendResult<T>> {
  const accessToken = init.accessToken ?? (await auth.getSession())?.accessToken;
  if (!accessToken) return { ok: false, status: 401, error: "Not signed in" };

  const incoming = await headers();
  const forwarded: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "X-Request-ID": crypto.randomUUID(),
    // Lets the audit trail record the real browser, not "node". The backend only trusts
    // X-Forwarded-For from proxies listed in uvicorn's --forwarded-allow-ips.
    "User-Agent": incoming.get("user-agent") ?? "next-server",
  };
  const xff = incoming.get("x-forwarded-for");
  if (xff) forwarded["X-Forwarded-For"] = xff;
  if (init.body !== undefined) forwarded["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${BACKEND_API_URL}${path}`, {
      method: init.method ?? "GET",
      headers: forwarded,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return { ok: false, status: 503, error: "Backend API is unreachable" };
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const error = typeof detail === "string" ? detail : `Request failed (${response.status})`;
    return { ok: false, status: response.status, error };
  }
  return { ok: true, status: response.status, data: payload as T };
}
