"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { backendFetch } from "@/lib/backend";
import { getAdminViewer } from "@/lib/dal";

export type ActionState = { ok: boolean; message: string } | null;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PORTAL_INTENTS = new Set(["sso", "domain_verification"]);

// Server Actions are public HTTP endpoints. Each one re-checks the caller here (fast, friendly error)
// and the Python API checks again (authoritative) before anything changes.
async function denyUnlessAdmin(): Promise<ActionState> {
  return (await getAdminViewer()) ? null : { ok: false, message: "Admin role required" };
}

export async function changeRoleAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const denied = await denyUnlessAdmin();
  if (denied) return denied;

  const userId = String(formData.get("userId") ?? "");
  const role = String(formData.get("role") ?? "");
  if (!UUID.test(userId) || (role !== "user" && role !== "admin")) {
    return { ok: false, message: "Invalid input" };
  }

  const result = await backendFetch(`/api/v1/users/${userId}/role`, { method: "PATCH", body: { role } });
  if (!result.ok) return { ok: false, message: result.error };
  refresh();
  return { ok: true, message: `Role set to ${role}` };
}

export async function setStatusAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const denied = await denyUnlessAdmin();
  if (denied) return denied;

  const userId = String(formData.get("userId") ?? "");
  const isActive = formData.get("isActive");
  if (!UUID.test(userId) || (isActive !== "true" && isActive !== "false")) {
    return { ok: false, message: "Invalid input" };
  }

  const result = await backendFetch<{ sessions_revoked: number }>(`/api/v1/users/${userId}/status`, {
    method: "PATCH",
    body: { is_active: isActive === "true" },
  });
  if (!result.ok) return { ok: false, message: result.error };
  refresh();
  return {
    ok: true,
    message:
      isActive === "true"
        ? "Access restored"
        : `Suspended; ${result.data.sessions_revoked} active session(s) ended`,
  };
}

export async function openAdminPortalAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const denied = await denyUnlessAdmin();
  if (denied) return denied;
  if (!auth.features.adminPortal) return { ok: false, message: "The Admin Portal needs AUTH_PROVIDER=workos" };

  const intent = String(formData.get("intent") ?? "");
  if (!PORTAL_INTENTS.has(intent)) return { ok: false, message: "Invalid input" };

  const result = await backendFetch<{ link: string }>("/api/v1/admin/portal-link", {
    method: "POST",
    body: { intent },
  });
  if (!result.ok) return { ok: false, message: result.error };
  // One-time, short-lived link. Redirect straight to it; never store or email it.
  redirect(result.data.link);
}
