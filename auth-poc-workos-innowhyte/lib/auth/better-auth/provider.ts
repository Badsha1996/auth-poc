import "server-only";
import { getSessionCookie } from "better-auth/cookies";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { NextResponse, type NextRequest } from "next/server";
import type { AuthProvider, AuthSession } from "../types";
import { getBetterAuth } from "./server";

/**
 * Better Auth implementation of the app's AuthProvider contract.
 *
 * Differences from WorkOS that the contract hides:
 * - Login pages are ours (app/auth/sign-in etc.) instead of a hosted page.
 * - OAuth callbacks are handled by Better Auth's own route (/api/auth/[...all]), so /auth/callback is
 *   unused; the user row is created by lib/dal.ts on the first page load (the same self-heal path).
 * - The session is a database session; the bearer token for the Python API is a 15-minute JWT minted
 *   from it on demand.
 */

export const BETTER_AUTH_PAGES = {
  signIn: "/auth/sign-in",
  signUp: "/auth/sign-up",
  forgotPassword: "/auth/forgot-password",
  resetPassword: "/auth/reset-password",
} as const;

// Always reachable without a session, on top of the app's own public paths.
const PUBLIC_PATHS = ["/api/auth", ...Object.values(BETTER_AUTH_PAGES)];

/** "/" matches only itself; any other entry also matches everything below it. */
function isPublicPath(pathname: string, publicPaths: string[]) {
  return publicPaths.some((p) => pathname === p || (p !== "/" && pathname.startsWith(`${p}/`)));
}

export const betterAuthProvider: AuthProvider = {
  name: "better-auth",
  features: { adminPortal: false },

  async getSession(): Promise<AuthSession | null> {
    const betterAuth = getBetterAuth();
    const requestHeaders = await headers();
    const result = await betterAuth.api.getSession({ headers: requestHeaders });
    if (!result) return null;
    // The JWT for the Python API (claims defined in server.ts). Never sent to the browser.
    const { token } = await betterAuth.api.getToken({ headers: requestHeaders });
    const { user, session } = result;
    return {
      provider: "better-auth",
      user: {
        id: user.id,
        email: user.email,
        firstName: user.name || null,
        lastName: null,
        avatarUrl: user.image ?? null,
      },
      accessToken: token,
      sessionId: session.id,
    };
  },

  getSignInUrl: async () => BETTER_AUTH_PAGES.signIn,
  getSignUpUrl: async () => BETTER_AUTH_PAGES.signUp,

  async signOut() {
    await getBetterAuth().api.signOut({ headers: await headers() });
    redirect("/");
  },

  callbackHandler() {
    // Not used by Better Auth (see above); keeps old links to /auth/callback harmless.
    return async (request: NextRequest) => NextResponse.redirect(new URL("/", request.url));
  },

  proxy({ publicPaths }) {
    const allPublic = [...publicPaths, ...PUBLIC_PATHS];
    return (request: NextRequest) => {
      // Cookie presence only: a cheap gate. Pages still validate the session through lib/dal.ts and the
      // Python API verifies every token, so a forged cookie gets nowhere.
      if (isPublicPath(request.nextUrl.pathname, allPublic) || getSessionCookie(request)) {
        return NextResponse.next();
      }
      return NextResponse.redirect(new URL(BETTER_AUTH_PAGES.signIn, request.url));
    };
  },
};
