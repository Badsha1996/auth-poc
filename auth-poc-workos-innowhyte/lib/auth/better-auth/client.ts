import { createAuthClient } from "better-auth/react";

/** Browser-side Better Auth client. Talks to /api/auth on this same origin. */
export const authClient = createAuthClient();
