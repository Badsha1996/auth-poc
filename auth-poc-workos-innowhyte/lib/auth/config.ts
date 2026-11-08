import { AUTH_PROVIDER_NAMES, type AuthProviderName } from "./types";

/**
 * Which identity provider this deployment runs on. Read from AUTH_PROVIDER (default "workos").
 * An unknown value stops the app instead of silently falling back to another provider.
 */
export function authProviderName(): AuthProviderName {
  const value = (process.env.AUTH_PROVIDER ?? "workos").trim();
  if (!(AUTH_PROVIDER_NAMES as readonly string[]).includes(value)) {
    throw new Error(`Unknown AUTH_PROVIDER "${value}". Use one of: ${AUTH_PROVIDER_NAMES.join(", ")}`);
  }
  return value as AuthProviderName;
}
