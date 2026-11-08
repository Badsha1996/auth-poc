import {
  authkitProxy,
  getSignInUrl,
  getSignUpUrl,
  handleAuth,
  signOut,
  withAuth,
} from "@workos-inc/authkit-nextjs";
import type { User } from "@workos-inc/node";
import type { AuthProvider, AuthSession, AuthUser } from "./types";

/**
 * WorkOS AuthKit implementation.
 *
 * Session security handled by @workos-inc/authkit-nextjs:
 * - Hosted login (passwords, MFA, Google/Microsoft OAuth, Entra ID SSO) - no credentials touch our app.
 * - Session = encrypted, httpOnly, SameSite=Lax cookie (sealed with WORKOS_COOKIE_PASSWORD).
 * - Short-lived access token + rotating refresh token; the proxy refreshes before expiry.
 * - Access tokens are verified against WorkOS JWKS, including the issuer when WORKOS_ISSUER is set.
 */
function toAuthUser(user: User): AuthUser {
  return {
    id: user.id,
    email: user.email,
    firstName: user.firstName ?? null,
    lastName: user.lastName ?? null,
    avatarUrl: user.profilePictureUrl ?? null,
  };
}

export const workosProvider: AuthProvider = {
  name: "workos",
  features: { adminPortal: true },

  async getSession(): Promise<AuthSession | null> {
    const info = await withAuth();
    if (!info.user) return null;
    return {
      provider: "workos",
      user: toAuthUser(info.user),
      accessToken: info.accessToken,
      sessionId: info.sessionId,
    };
  },

  getSignInUrl: () => getSignInUrl(),
  getSignUpUrl: () => getSignUpUrl(),

  async signOut() {
    await signOut();
  },

  callbackHandler(options = {}) {
    return handleAuth({
      returnPathname: "/",
      onSuccess: async (data) => {
        if (!options.onSignedIn) return;
        // Already verified by handleAuth; we only read the session id claim (JWT payloads are base64url).
        const payload = Buffer.from(data.accessToken.split(".")[1], "base64url").toString("utf8");
        const sessionId = String(JSON.parse(payload).sid ?? "");
        await options.onSignedIn({
          provider: "workos",
          user: toAuthUser(data.user),
          accessToken: data.accessToken,
          sessionId,
        });
      },
    });
  },

  proxy({ publicPaths }) {
    return authkitProxy({
      middlewareAuth: { enabled: true, unauthenticatedPaths: publicPaths },
      // Refresh the access token a minute early so backend calls never carry an about-to-expire token.
      refreshBufferSeconds: 60,
    });
  },
};
