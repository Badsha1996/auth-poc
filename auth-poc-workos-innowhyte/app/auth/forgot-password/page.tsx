import { Suspense } from "react";
import { Card, Shell } from "@/components/ui";
import { ForgotPasswordForm } from "../_components/forms";
import { guardBetterAuthPage } from "../_components/guard";

async function Content() {
  await guardBetterAuthPage();
  return (
    <Card title="Reset your password">
      <ForgotPasswordForm />
    </Card>
  );
}

export default function ForgotPasswordPage() {
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
