import { microsoftEntraId } from "better-auth/plugins";

/**
 * Social and enterprise sign-in for Better Auth.
 *
 * Every provider is listed once in PROVIDERS. A provider is switched on only when all of its
 * environment variables are set, so the sign-in page never shows a button that cannot work.
 * In development the sign-in page lists the providers that are switched off and the variables they need.
 *
 * Callback URL to register with each provider: {BETTER_AUTH_URL}/api/auth/callback/{id}
 *
 * Two kinds of provider:
 * - "social": built into Better Auth (passed to betterAuth({ socialProviders })).
 * - "oidc":   added through the genericOAuth plugin (passed to genericOAuth({ config })).
 * Both sign in through the same authClient.signIn.social({ provider: id }) call and the same callback route.
 *
 * To add another provider (GitLab, Discord, Apple, Okta, ...), add one entry to PROVIDERS.
 */
export type SocialProviderId = "google" | "microsoft" | "microsoft-entra-id" | "github";

export interface SocialProviderInfo {
  id: SocialProviderId;
  label: string;
}

export interface SocialProviderStatus extends SocialProviderInfo {
  enabled: boolean;
  /** Variables that must all be set to switch the provider on. */
  requiredEnv: string[];
  /** Variables that are required but empty. */
  missingEnv: string[];
}

const env = (name: string) => process.env[name]?.trim() || undefined;

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type ProviderDefinition =
  | { kind: "social"; id: SocialProviderId; label: string; requiredEnv: string[]; build: () => object }
  | {
      kind: "oidc";
      id: SocialProviderId;
      label: string;
      requiredEnv: string[];
      build: () => ReturnType<typeof microsoftEntraId>;
    };

const PROVIDERS: ProviderDefinition[] = [
  {
    kind: "social",
    id: "google",
    label: "Continue with Google",
    requiredEnv: ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
    build: () => ({ clientId: env("GOOGLE_CLIENT_ID")!, clientSecret: env("GOOGLE_CLIENT_SECRET")! }),
  },
  {
    // Personal Microsoft accounts and/or work accounts from any organisation, chosen by MICROSOFT_TENANT_ID:
    // "common" (default) = both, "organizations" = any work/school account, "consumers" = personal only,
    // a tenant GUID = one organisation (but prefer the Entra ID provider below for that).
    kind: "social",
    id: "microsoft",
    label: "Continue with Microsoft",
    requiredEnv: ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"],
    build: () => ({
      clientId: env("MICROSOFT_CLIENT_ID")!,
      clientSecret: env("MICROSOFT_CLIENT_SECRET")!,
      tenantId: env("MICROSOFT_TENANT_ID") ?? "common",
    }),
  },
  {
    // Your organisation's Microsoft Entra ID only (work accounts in one tenant). Needs a real tenant GUID.
    kind: "oidc",
    id: "microsoft-entra-id",
    label: "Continue with Microsoft Entra ID",
    requiredEnv: ["ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET", "ENTRA_TENANT_ID"],
    build: () => {
      const tenantId = env("ENTRA_TENANT_ID")!;
      if (!GUID.test(tenantId)) {
        throw new Error(
          `ENTRA_TENANT_ID must be your Directory (tenant) ID, a GUID like 00000000-0000-0000-0000-000000000000. ` +
            `Got "${tenantId}". For "common", "organizations" or "consumers" use MICROSOFT_* instead.`,
        );
      }
      return microsoftEntraId({
        clientId: env("ENTRA_CLIENT_ID")!,
        clientSecret: env("ENTRA_CLIENT_SECRET")!,
        tenantId,
      });
    },
  },
  {
    kind: "social",
    id: "github",
    label: "Continue with GitHub",
    requiredEnv: ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
    build: () => ({ clientId: env("GITHUB_CLIENT_ID")!, clientSecret: env("GITHUB_CLIENT_SECRET")! }),
  },
];

function isEnabled(p: ProviderDefinition) {
  return p.requiredEnv.every((name) => env(name));
}

/** Built-in providers for betterAuth({ socialProviders }). */
export function socialProviderConfig(): Record<string, object> {
  const config: Record<string, object> = {};
  for (const p of PROVIDERS) if (p.kind === "social" && isEnabled(p)) config[p.id] = p.build();
  return config;
}

/** OIDC providers for genericOAuth({ config }). Empty when none are configured. */
export function genericOAuthProviderConfig() {
  return PROVIDERS.filter((p) => p.kind === "oidc" && isEnabled(p)).map((p) =>
    (p as Extract<ProviderDefinition, { kind: "oidc" }>).build(),
  );
}

/** Every known provider and whether it is switched on (for the development hint on the sign-in page). */
export function socialProviderStatus(): SocialProviderStatus[] {
  return PROVIDERS.map((p) => ({
    id: p.id,
    label: p.label,
    enabled: isEnabled(p),
    requiredEnv: p.requiredEnv,
    missingEnv: p.requiredEnv.filter((name) => !env(name)),
  }));
}

/**
 * Providers whose email Better Auth may trust when linking a sign-in to an existing user with the same email.
 *
 * Microsoft work-account tokens usually carry no email_verified claim, so without this every Microsoft
 * sign-in by someone who already has an account fails with "account_not_linked".
 *
 * Trusted only when locked to ONE tenant you control: your directory admins decide who owns which email.
 * Never with "common" / "organizations": an admin of any other tenant can put your email on one of their
 * users and take over your account through linking ("nOAuth"). Google and GitHub need no entry here:
 * they report email_verified themselves.
 */
export function trustedLinkingProviders(): SocialProviderId[] {
  const trusted: SocialProviderId[] = [];
  const msTenant = env("MICROSOFT_TENANT_ID");
  if (isEnabled(PROVIDERS.find((p) => p.id === "microsoft")!) && msTenant && GUID.test(msTenant)) {
    trusted.push("microsoft");
  }
  if (isEnabled(PROVIDERS.find((p) => p.id === "microsoft-entra-id")!)) trusted.push("microsoft-entra-id");
  return trusted;
}

/** The buttons to show, in display order. */
export function enabledSocialProviders(): SocialProviderInfo[] {
  return PROVIDERS.filter(isEnabled).map(({ id, label }) => ({ id, label }));
}
