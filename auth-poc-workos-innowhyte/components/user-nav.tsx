import Link from "next/link";
import { connection } from "next/server";
import { signOutAction } from "@/app/auth/actions";
import { getViewerState } from "@/lib/dal";
import { Badge, buttonClass, primaryButtonClass } from "./ui";

/** Request-time header nav. Render inside <Suspense>. */
export async function UserNav() {
  await connection();
  const state = await getViewerState();

  if (state.status === "setup-failed") {
    return (
      <nav className="flex gap-2">
        <form action={signOutAction}>
          <button type="submit" className={buttonClass}>
            Sign out
          </button>
        </form>
      </nav>
    );
  }

  if (state.status === "signed-out") {
    return (
      <nav className="flex gap-2">
        <a href="/sign-in" className={buttonClass}>
          Sign in
        </a>
        <a href="/sign-up" className={primaryButtonClass}>
          Sign up
        </a>
      </nav>
    );
  }

  const { user } = state.viewer;
  return (
    <nav className="flex items-center gap-3 text-sm">
      <Link href="/demo" className="hover:underline">
        Role demo
      </Link>
      {user.role === "admin" && user.isActive && (
        <Link href="/admin" className="hover:underline">
          Admin board
        </Link>
      )}
      <span className="hidden text-zinc-500 sm:inline">{user.email}</span>
      <Badge tone={user.role === "admin" ? "admin" : "user"}>{user.role}</Badge>
      <form action={signOutAction}>
        <button type="submit" className={buttonClass}>
          Sign out
        </button>
      </form>
    </nav>
  );
}
