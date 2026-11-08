import Link from "next/link";
import { Suspense } from "react";
import { Card, Shell } from "@/components/ui";
import { ResetPasswordForm } from "../_components/forms";
import { guardBetterAuthPage } from "../_components/guard";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

// Better Auth redirects here from the emailed link with ?token=... (or ?error=INVALID_TOKEN).
async function Content({ searchParams }: { searchParams: SearchParams }) {
  await guardBetterAuthPage({ allowSignedIn: true });
  const { token, error } = await searchParams;

  if (typeof token !== "string" || !token || error) {
    return (
      <Card title="Link expired">
        <p className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
          This reset link is invalid or has already been used.
        </p>
        <Link href="/auth/forgot-password" className="text-sm underline">
          Send a new link
        </Link>
      </Card>
    );
  }
  return (
    <Card title="Choose a new password">
      <ResetPasswordForm token={token} />
    </Card>
  );
}

export default function ResetPasswordPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <Shell>
      <div className="mx-auto max-w-sm">
        <Suspense fallback={<p className="text-sm text-zinc-500">Loading…</p>}>
          <Content searchParams={searchParams} />
        </Suspense>
      </div>
    </Shell>
  );
}
