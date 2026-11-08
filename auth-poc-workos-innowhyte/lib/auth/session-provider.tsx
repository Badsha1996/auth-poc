import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import type { ReactNode } from "react";
import { BetterAuthSessionKeeper } from "./better-auth/session-keeper";
import { authProviderName } from "./config";

/** Client-side session plumbing for whichever provider AUTH_PROVIDER selects. Rendered in app/layout.tsx. */
export function AuthSessionProvider({ children }: { children: ReactNode }) {
  if (authProviderName() === "better-auth") {
    return (
      <>
        <BetterAuthSessionKeeper />
        {children}
      </>
    );
  }
  return <AuthKitProvider>{children}</AuthKitProvider>;
}
