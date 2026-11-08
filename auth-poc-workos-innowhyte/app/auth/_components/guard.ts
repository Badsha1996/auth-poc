import "server-only";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import { auth } from "@/lib/auth";

/**
 * The app's own login pages exist only for Better Auth. With WorkOS they forward to /sign-in, which
 * redirects to the hosted WorkOS page. Signed-in visitors are sent home.
 */
export async function guardBetterAuthPage({ allowSignedIn = false } = {}) {
  await connection();
  if (auth.name !== "better-auth") redirect("/sign-in");
  if (!allowSignedIn && (await auth.getSession())) redirect("/");
}
