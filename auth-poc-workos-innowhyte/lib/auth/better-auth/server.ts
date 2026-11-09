import { betterAuth, type BetterAuthOptions } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { genericOAuth, jwt } from "better-auth/plugins";
import { Pool } from "pg";
import { sendAuthEmail } from "./email";
import { genericOAuthProviderConfig, socialProviderConfig, trustedLinkingProviders } from "./social";

/*
 * Better Auth server instance (used when AUTH_PROVIDER=better-auth).
 *
 * Relative imports only and no "server-only": scripts/better-auth-migrate.ts loads this file outside Next.js.
 *
 * Data: Better Auth keeps its own tables (user, session, account, verification, jwks) in
 * BETTER_AUTH_DATABASE_URL. Use a separate database from DATABASE_URL: the Python API owns that one
 * through Alembic, and Prisma there is read-only. The app's users/roles still live in DATABASE_URL and
 * are written only by the Python API, exactly as with WorkOS.
 *
 * Tokens: the JWT plugin mints the short-lived access token the Python API verifies. It is signed with
 * EdDSA, issuer and audience are BETTER_AUTH_URL, and public keys are served at /api/auth/jwks. The Python
 * API's BetterAuthProvider expects exactly these values.
 */

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`AUTH_PROVIDER=better-auth requires ${name}`);
  return value;
}

export function betterAuthOptions() {
  const baseURL = required("BETTER_AUTH_URL").replace(/\/+$/, "");
  const secret = required("BETTER_AUTH_SECRET");
  if (secret.length < 32) throw new Error("BETTER_AUTH_SECRET must be at least 32 characters");
  // Enterprise OIDC providers (e.g. one Microsoft Entra ID tenant). Same sign-in call and callback route
  // as the built-in social providers; see lib/auth/better-auth/social.ts.
  const oidcProviders = genericOAuthProviderConfig();

  return {
    appName: "Innowhyte",
    baseURL,
    secret,
    database: new Pool({ connectionString: required("BETTER_AUTH_DATABASE_URL"), max: 5 }),
    emailAndPassword: {
      enabled: true,
      requireEmailVerification: true,
      minPasswordLength: 12,
      revokeSessionsOnPasswordReset: true,
      sendResetPassword: async ({ user, url }) =>
        sendAuthEmail({ to: user.email, subject: "Reset your password", url }),
    },
    emailVerification: {
      sendOnSignUp: true,
      autoSignInAfterVerification: true,
      sendVerificationEmail: async ({ user, url }) =>
        sendAuthEmail({ to: user.email, subject: "Verify your email", url }),
    },
    socialProviders: socialProviderConfig(),
    account: {
      accountLinking: {
        // Link a social sign-in to an existing user with the same email only when the provider verified
        // the email, or is single-tenant Microsoft (see trustedLinkingProviders). The existing user's own
        // email must be verified too (Better Auth's default requireLocalEmailVerified).
        trustedProviders: trustedLinkingProviders(),
      },
    },
    session: {
      expiresIn: 60 * 60 * 24 * 7, // 7 days, extended while in use
      updateAge: 60 * 60 * 24,
      // Saves a database read per request. Roles and suspension are not in this cache; they come from
      // our own users table on every request.
      cookieCache: { enabled: true, maxAge: 5 * 60 },
    },
    plugins: [
      jwt({
        jwks: { keyPairConfig: { alg: "EdDSA", crv: "Ed25519" } },
        jwt: {
          issuer: baseURL,
          audience: baseURL,
          expirationTime: "15m",
          // Everything the Python API needs to create the user row, so it never calls back here.
          definePayload: ({ user, session }) => ({
            email: user.email,
            emailVerified: user.emailVerified,
            name: user.name,
            image: user.image ?? undefined,
            sid: session.id,
          }),
        },
      }),
      ...(oidcProviders.length ? [genericOAuth({ config: oidcProviders })] : []),
      nextCookies(), // must stay last: lets Server Actions set and clear the session cookie
    ],
  } satisfies BetterAuthOptions;
}

function createBetterAuth() {
  return betterAuth(betterAuthOptions());
}

// Kept on globalThis so dev hot reloads reuse one instance (and one connection pool), like lib/db.ts.
const globalForAuth = globalThis as unknown as { betterAuth?: ReturnType<typeof createBetterAuth> };

/** Created on first use, so a WorkOS deployment never needs any BETTER_AUTH_* variable. */
export function getBetterAuth() {
  globalForAuth.betterAuth ??= createBetterAuth();
  return globalForAuth.betterAuth;
}
