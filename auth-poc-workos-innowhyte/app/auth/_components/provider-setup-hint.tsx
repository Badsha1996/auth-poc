import "server-only";
import { socialProviderStatus } from "@/lib/auth/better-auth/social";

/**
 * Development only: lists sign-in providers that are switched off and the .env variables they need,
 * so a missing button explains itself. Renders nothing in production (variable names are not for visitors).
 */
export function ProviderSetupHint() {
  if (process.env.NODE_ENV === "production") return null;
  const off = socialProviderStatus().filter((p) => !p.enabled);
  if (off.length === 0) return null;
  const baseURL = (process.env.BETTER_AUTH_URL ?? "http://localhost:3000").replace(/\/+$/, "");

  return (
    <details className="rounded border border-dashed border-zinc-300 p-2 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
      <summary className="cursor-pointer">Development: {off.length} sign-in provider(s) not configured</summary>
      <ul className="mt-2 grid gap-2">
        {off.map((p) => (
          <li key={p.id}>
            <strong>{p.label.replace("Continue with ", "")}</strong>: set{" "}
            {p.missingEnv.map((name, i) => (
              <span key={name}>
                {i > 0 && ", "}
                <code>{name}</code>
              </span>
            ))}{" "}
            in <code>.env</code>, then restart. Callback URL: <code>{`${baseURL}/api/auth/callback/${p.id}`}</code>
          </li>
        ))}
      </ul>
    </details>
  );
}
