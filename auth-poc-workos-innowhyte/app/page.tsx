import Link from "next/link";
import { Suspense } from "react";
import { connection } from "next/server";
import { Badge, Card, Shell, buttonClass, formatDate, primaryButtonClass } from "@/components/ui";
import { UserNav } from "@/components/user-nav";
import { signOutAction } from "@/app/auth/actions";
import { getViewerState } from "@/lib/dal";

async function Welcome() {
  await connection();
  const state = await getViewerState();

  if (state.status === "setup-failed") {
    return (
      <Card title="Signed in, but your account could not be set up">
        <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">
          You are signed in, but the API could not create or load your account, so nothing is available yet.
          Reloading retries the setup.
        </p>
        <p className="mb-4 break-words rounded bg-red-50 p-2 font-mono text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
          {state.error}
        </p>
        <form action={signOutAction}>
          <button type="submit" className={buttonClass}>
            Sign out
          </button>
        </form>
      </Card>
    );
  }

  if (state.status === "signed-out") {
    return (
      <Card title="Innowhyte POC Auth">
        <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
          Sign in with email, Google or Microsoft. New accounts start with the <b>user</b> role;
          an admin can promote you from the admin board.
        </p>
        <div className="flex gap-2">
          <a href="/sign-in" className={buttonClass}>
            Sign in
          </a>
          <a href="/sign-up" className={primaryButtonClass}>
            Create account
          </a>
        </div>
      </Card>
    );
  }

  const { user } = state.viewer;
  return (
    <Card title={`Welcome, ${user.fullName ?? user.email}`} aside={<Badge tone={user.role === "admin" ? "admin" : "user"}>{user.role}</Badge>}>
      <dl className="mb-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-zinc-500">Email</dt>
        <dd>{user.email}</dd>
        <dt className="text-zinc-500">Role (from database)</dt>
        <dd>{user.role}</dd>
        <dt className="text-zinc-500">Last sign-in</dt>
        <dd>{formatDate(user.lastLoginAt)}</dd>
      </dl>
      {!user.isActive && (
        <p className="mb-4 text-sm text-red-600">Your access is suspended. Contact an administrator.</p>
      )}
      <div className="flex gap-2">
        <Link href="/demo" className={primaryButtonClass}>
          Try the role demo
        </Link>
        {user.role === "admin" && user.isActive && (
          <Link href="/admin" className={buttonClass}>
            Open admin board
          </Link>
        )}
      </div>
    </Card>
  );
}

export default function Home() {
  return (
    <Shell
      nav={
        <Suspense fallback={null}>
          <UserNav />
        </Suspense>
      }
    >
      <Suspense fallback={<p className="text-sm text-zinc-500">Loading…</p>}>
        <Welcome />
      </Suspense>
    </Shell>
  );
}
