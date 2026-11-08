import "server-only";
import { cache } from "react";
import { redirect } from "next/navigation";
import { auth, type AuthSession } from "@/lib/auth";
import { backendFetch } from "@/lib/backend";
import { prisma } from "@/lib/db";
import type { User } from "@/lib/generated/prisma/client";

/**
 * Data Access Layer: the only place pages and actions get "who is this and what may they do".
 * Reads are fresh on every request (no caching) so a role change or suspension shows up at once.
 * These checks drive the UI; the Python API re-checks everything it is asked to do.
 */
export type AppUser = Pick<
  User,
  "id" | "email" | "fullName" | "avatarUrl" | "role" | "isActive" | "lastLoginAt"
>;

export interface Viewer {
  session: AuthSession;
  user: AppUser;
}

const select = {
  id: true,
  email: true,
  fullName: true,
  avatarUrl: true,
  role: true,
  isActive: true,
  lastLoginAt: true,
} as const;

async function findUser(session: AuthSession) {
  return prisma.user.findUnique({
    where: {
      authProvider_externalId: { authProvider: session.provider, externalId: session.user.id },
    },
    select,
  });
}

/**
 * "Signed in with the identity provider" and "has an account row" are different things. Keeping them
 * apart stops a failed account sync from looking like a signed-out visitor (which sent people round a
 * sign-in loop: WorkOS already has a session, so it bounces straight back).
 */
export type ViewerState =
  | { status: "signed-out" }
  | { status: "setup-failed"; error: string }
  | { status: "ready"; viewer: Viewer };

/**
 * Self-heals if the post-login sync was missed.
 * React cache() de-duplicates it within one request only (nav + page share one lookup).
 */
export const getViewerState = cache(async function getViewerState(): Promise<ViewerState> {
  const session = await auth.getSession();
  if (!session) return { status: "signed-out" };

  let user = await findUser(session);
  if (!user) {
    const synced = await backendFetch("/api/v1/users/sync", {
      method: "POST",
      accessToken: session.accessToken,
    });
    if (!synced.ok) {
      console.error(`user sync failed (${synced.status}): ${synced.error}`);
      return { status: "setup-failed", error: synced.error };
    }
    user = await findUser(session);
    if (!user) return { status: "setup-failed", error: "Account was not found after sync" };
  }
  return { status: "ready", viewer: { session, user } };
});

/** Signed-in viewer with their DB role, or null. */
export async function getViewer(): Promise<Viewer | null> {
  const state = await getViewerState();
  return state.status === "ready" ? state.viewer : null;
}

/** For pages that need an account: signed out -> sign in; signed in without an account -> home, which says why. */
export async function requireViewer(): Promise<Viewer> {
  const state = await getViewerState();
  if (state.status === "signed-out") redirect("/sign-in");
  if (state.status === "setup-failed") redirect("/");
  return state.viewer;
}

export async function getAdminViewer(): Promise<Viewer | null> {
  const viewer = await getViewer();
  return viewer && viewer.user.isActive && viewer.user.role === "admin" ? viewer : null;
}
