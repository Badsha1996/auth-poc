import "server-only";
import { betterAuthProvider } from "./better-auth/provider";
import { authProviderName } from "./config";
import type { AuthProvider, AuthProviderName } from "./types";
import { workosProvider } from "./workos";

export type { AuthFeatures, AuthProvider, AuthProviderName, AuthSession, AuthUser } from "./types";

/**
 * The one place that knows which identity provider this deployment uses. Pages, actions, the proxy and
 * the backend client only ever import `auth` from here.
 *
 * Switch with AUTH_PROVIDER=workos | better-auth (and the same value in the Python API's .env), then
 * restart the dev server or redeploy. Both implementations are safe to import when unconfigured: each one
 * reads its settings only when it is first used.
 */
const providers: Record<AuthProviderName, AuthProvider> = {
  workos: workosProvider,
  "better-auth": betterAuthProvider,
};

export const auth: AuthProvider = providers[authProviderName()];
