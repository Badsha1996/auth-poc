/**
 * Social sign-in for Better Auth. A provider is offered only when both its id and secret are set,
 * so the sign-in page never shows a button that cannot work.
 */
export type SocialProviderId = "google" | "microsoft";

export interface SocialProviderInfo {
  id: SocialProviderId;
  label: string;
}

const env = (name: string) => process.env[name]?.trim() || undefined;

export function socialProviderConfig() {
  const config: {
    google?: { clientId: string; clientSecret: string };
    microsoft?: { clientId: string; clientSecret: string; tenantId: string };
  } = {};

  const googleId = env("GOOGLE_CLIENT_ID");
  const googleSecret = env("GOOGLE_CLIENT_SECRET");
  if (googleId && googleSecret) config.google = { clientId: googleId, clientSecret: googleSecret };

  const msId = env("MICROSOFT_CLIENT_ID");
  const msSecret = env("MICROSOFT_CLIENT_SECRET");
  if (msId && msSecret) {
    // "common" = any Microsoft account; set your Entra tenant id to allow only your organisation.
    config.microsoft = { clientId: msId, clientSecret: msSecret, tenantId: env("MICROSOFT_TENANT_ID") ?? "common" };
  }
  return config;
}

export function enabledSocialProviders(): SocialProviderInfo[] {
  const config = socialProviderConfig();
  const list: SocialProviderInfo[] = [];
  if (config.google) list.push({ id: "google", label: "Continue with Google" });
  if (config.microsoft) list.push({ id: "microsoft", label: "Continue with Microsoft" });
  return list;
}
