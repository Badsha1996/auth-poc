import type { NextProxy, NextRequest } from "next/server";

/**
 * Provider-neutral authentication contract.
 *
 * Application code imports `auth` from "@/lib/auth" and only ever sees these types. WorkOS is the
 * implementation today (lib/auth/workos.ts). A fully isolated deployment can add another
 * implementation (for example Better Auth) without touching pages, actions or the backend client.
 *
 * Authentication only: who is signed in. Authorization (roles, suspension) lives in our own
 * database and is enforced by the Python backend.
 */
/**
 * The identity providers this app can run on, chosen with AUTH_PROVIDER.
 * The same name is stored in users.auth_provider and must equal the Python API's AUTH_PROVIDER.
 */
export const AUTH_PROVIDER_NAMES = ["workos", "better-auth"] as const;
export type AuthProviderName = (typeof AUTH_PROVIDER_NAMES)[number];

export interface AuthUser {
  /** Stable user id at the identity provider (the JWT "sub"). */
  id: string;
  email: string;
  firstName: string | null;
  lastName: string | null;
  avatarUrl: string | null;
}

export interface AuthSession {
  /** Matches users.auth_provider in the database. */
  provider: AuthProviderName;
  user: AuthUser;
  /** Short-lived bearer token for the backend API. Never send it to the browser. */
  accessToken: string;
  sessionId: string;
}

export interface CallbackOptions {
  /** Runs once after a successful sign-in, before the user is redirected into the app. */
  onSignedIn?: (session: AuthSession) => Promise<void>;
}

export interface ProxyOptions {
  /** Paths reachable without a session. Everything else redirects to sign-in. */
  publicPaths: string[];
}

export interface AuthFeatures {
  /** WorkOS Admin Portal (self-serve SSO and domain setup for a customer's IT admin). */
  adminPortal: boolean;
}

export interface AuthProvider {
  readonly name: AuthProviderName;
  readonly features: AuthFeatures;
  /** The current session, or null. Request-time only (reads cookies). */
  getSession(): Promise<AuthSession | null>;
  /** Route Handlers / Server Actions only: they set PKCE cookies. */
  getSignInUrl(): Promise<string>;
  getSignUpUrl(): Promise<string>;
  /** Server Actions only (POST). Ends the session at the provider too. */
  signOut(): Promise<void>;
  callbackHandler(options?: CallbackOptions): (request: NextRequest) => Promise<Response>;
  proxy(options: ProxyOptions): NextProxy;
}
