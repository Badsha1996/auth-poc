import { Suspense } from "react";
import { Card, Shell } from "@/components/ui";
import { enabledSocialProviders } from "@/lib/auth/better-auth/social";
import { SignUpForm } from "../_components/forms";
import { guardBetterAuthPage } from "../_components/guard";
import { ProviderSetupHint } from "../_components/provider-setup-hint";

async function Content() {
  await guardBetterAuthPage();
  return (
    <Card title="Create your account">
      <div className="grid gap-4">
        <SignUpForm socialProviders={enabledSocialProviders()} />
        <ProviderSetupHint />
      </div>
    </Card>
  );
}

export default function SignUpPage() {
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
