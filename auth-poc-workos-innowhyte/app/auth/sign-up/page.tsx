import { Suspense } from "react";
import { Card, Shell } from "@/components/ui";
import { enabledSocialProviders } from "@/lib/auth/better-auth/social";
import { SignUpForm } from "../_components/forms";
import { guardBetterAuthPage } from "../_components/guard";

async function Content() {
  await guardBetterAuthPage();
  return (
    <Card title="Create your account">
      <SignUpForm socialProviders={enabledSocialProviders()} />
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
