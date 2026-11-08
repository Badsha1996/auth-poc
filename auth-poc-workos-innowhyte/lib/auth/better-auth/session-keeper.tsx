"use client";

import { useEffect } from "react";
import { authClient } from "./client";

/**
 * Server Components can read the Better Auth session but cannot write cookies, so a session used only
 * through server-rendered pages would never be extended and would expire after 7 days even while in use.
 * One background request per page load lets Better Auth refresh the session cookie.
 */
export function BetterAuthSessionKeeper() {
  useEffect(() => {
    authClient.getSession().catch(() => {
      // Offline or signed out: nothing to refresh.
    });
  }, []);
  return null;
}
