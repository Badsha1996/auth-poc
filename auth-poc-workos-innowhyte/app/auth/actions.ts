"use server";

import { auth } from "@/lib/auth";

// POST-only (Server Action) so sign-out can't be triggered by prefetching or an <img src>.
export async function signOutAction() {
  await auth.signOut();
}
