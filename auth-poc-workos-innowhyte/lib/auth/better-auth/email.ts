/**
 * Verification and password-reset emails for Better Auth.
 *
 * WorkOS sends these itself; with Better Auth they are ours to send. Development prints the link to the
 * Next.js terminal so you can click it. Production refuses until a real sender is wired in below
 * (Resend, Amazon SES, Postmark, ...): silently dropping a password-reset email is worse than failing.
 */
export interface AuthEmail {
  to: string;
  subject: string;
  /** One-time link containing the token. Never log it outside development. */
  url: string;
}

export async function sendAuthEmail(email: AuthEmail): Promise<void> {
  if (process.env.NODE_ENV !== "production") {
    console.info(`[auth email] to=${email.to} subject="${email.subject}"\n  ${email.url}`);
    return;
  }
  throw new Error(
    "No email sender configured for Better Auth. Implement sendAuthEmail in lib/auth/better-auth/email.ts.",
  );
}
