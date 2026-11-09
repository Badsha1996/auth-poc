import { Suspense } from "react";
import { Card, Shell } from "@/components/ui";
import { enabledSocialProviders } from "@/lib/auth/better-auth/social";
import { SignInForm } from "../_components/forms";
import { guardBetterAuthPage } from "../_components/guard";
import { ProviderSetupHint } from "../_components/provider-setup-hint";

async function Content() {
  await guardBetterAuthPage();
  return (
    <Card title="Sign in">
      <div className="grid gap-4">
        <SignInForm socialProviders={enabledSocialProviders()} />
        <ProviderSetupHint />
      </div>
    </Card>
  );
}

export default function SignInPage() {
  return (
    <Shell>
      <div className="mx-auto max-w-sm">
        <Suspense fallback={<p className="text-sm text-zinc-500">Loading…</p>}>
          <Content />
        </Suspense>
      </div>
    </Shell>
  );
}
