import { auth } from "@/lib/auth";

// Refreshes sessions on every request and redirects signed-out visitors to sign-in,
// except on these public paths. Pages and the Python API still check authorization themselves.
export default auth.proxy({
  publicPaths: ["/", "/sign-in", "/sign-up", "/auth/callback"],
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
