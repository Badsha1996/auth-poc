import { auth } from "@/lib/auth";
import { backendFetch } from "@/lib/backend";

// After sign-in (and first sign-up) the Python API creates/updates the user row and assigns the
// default role. The backend verifies this token itself and reads the profile from WorkOS directly.
export const GET = auth.callbackHandler({
  onSignedIn: async (session) => {
    const result = await backendFetch("/api/v1/users/sync", {
      method: "POST",
      accessToken: session.accessToken,
    });
    if (!result.ok) {
      // Don't block sign-in; the data access layer retries the sync on the next page load.
      console.error(`user sync failed after sign-in (${result.status}): ${result.error}`);
    }
  },
});
