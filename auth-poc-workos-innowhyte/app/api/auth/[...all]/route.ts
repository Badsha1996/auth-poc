import { toNextJsHandler } from "better-auth/next-js";
import { notFound } from "next/navigation";
import type { NextRequest } from "next/server";
import { authProviderName } from "@/lib/auth/config";
import { getBetterAuth } from "@/lib/auth/better-auth/server";

// Better Auth's endpoints: sign-in/up, OAuth callbacks, email verification, password reset, JWKS, token.
// Only live when AUTH_PROVIDER=better-auth; with WorkOS this path does not exist.
async function handle(request: NextRequest) {
  if (authProviderName() !== "better-auth") notFound();
  const handler = toNextJsHandler(getBetterAuth());
  return request.method === "POST" ? handler.POST(request) : handler.GET(request);
}

export { handle as GET, handle as POST };
