import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";

// Initiate login URI: also used by WorkOS for invitations, password resets and bookmarked logins.
export async function GET() {
  redirect(await auth.getSignInUrl());
}
