import { Suspense } from "react";
import { connection } from "next/server";
import { Badge, Card, Shell } from "@/components/ui";
import { UserNav } from "@/components/user-nav";
import { backendFetch, type BackendResult } from "@/lib/backend";
import { requireViewer } from "@/lib/dal";

function Result({ title, endpoint, who, result }: { title: string; endpoint: string; who: string; result: BackendResult<unknown> }) {
  return (
    <Card
      title={title}
      aside={<Badge tone={result.ok ? "ok" : "bad"}>{result.ok ? `${result.status} allowed` : `${result.status} denied`}</Badge>}
    >
      <p className="mb-2 text-sm text-zinc-500">
        <code>GET {endpoint}</code> · {who}
      </p>
      <pre className="overflow-x-auto rounded bg-zinc-100 p-3 text-xs dark:bg-zinc-800">
        {JSON.stringify(result.ok ? result.data : { detail: result.error }, null, 2)}
      </pre>
    </Card>
  );
}

async function DemoResults() {
  await connection();
  await requireViewer();

  // Both calls carry the same access token. Python verifies it, then reads the role from the DB.
  const [member, admin] = await Promise.all([
    backendFetch("/api/v1/demo/member"),
    backendFetch("/api/v1/demo/admin"),
  ]);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Result title="Member area" endpoint="/api/v1/demo/member" who="any signed-in user" result={member} />
      <Result title="Admin area" endpoint="/api/v1/demo/admin" who="admins only" result={admin} />
    </div>
  );
}

export default function DemoPage() {
  return (
    <Shell
      nav={
        <Suspense fallback={null}>
          <UserNav />
        </Suspense>
      }
    >
      <h1 className="mb-1 text-xl font-semibold">Role demo</h1>
      <p className="mb-6 text-sm text-zinc-600 dark:text-zinc-400">
        The Next.js server calls the Python API with your WorkOS access token. Python verifies the
        token signature, issuer and expiry itself, then decides from the database role.
      </p>
      <Suspense fallback={<p className="text-sm text-zinc-500">Calling the Python API…</p>}>
        <DemoResults />
      </Suspense>
    </Shell>
  );
}
