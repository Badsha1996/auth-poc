"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { buttonClass, inputClass, labelClass, primaryButtonClass } from "@/components/ui";
import { authClient } from "@/lib/auth/better-auth/client";
import type { SocialProviderInfo } from "@/lib/auth/better-auth/social";

type Status = { tone: "error" | "info"; text: string } | null;

function Message({ status }: { status: Status }) {
  if (!status) return null;
  const tone =
    status.tone === "error"
      ? "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
      : "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200";
  return (
    <p role={status.tone === "error" ? "alert" : "status"} className={`rounded p-2 text-sm ${tone}`}>
      {status.text}
    </p>
  );
}

function SocialButtons({ providers, onError }: { providers: SocialProviderInfo[]; onError: (s: Status) => void }) {
  if (providers.length === 0) return null;
  return (
    <div className="grid gap-2">
      {providers.map((p) => (
        <button
          key={p.id}
          type="button"
          className={buttonClass}
          onClick={async () => {
            // Redirects to Google/Microsoft; only returns here on an error.
            const { error } = await authClient.signIn.social({ provider: p.id, callbackURL: "/" });
            if (error) onError({ tone: "error", text: error.message ?? "Could not start sign-in" });
          }}
        >
          {p.label}
        </button>
      ))}
      <p className="text-center text-xs text-zinc-500">or use your email</p>
    </div>
  );
}

const field = (form: HTMLFormElement, name: string) => String(new FormData(form).get(name) ?? "");

export function SignInForm({ socialProviders }: { socialProviders: SocialProviderInfo[] }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setStatus(null);
    const form = event.currentTarget;
    const { error } = await authClient.signIn.email({
      email: field(form, "email"),
      password: field(form, "password"),
      callbackURL: "/",
    });
    if (error) {
      setPending(false);
      setStatus({
        tone: "error",
        text:
          error.status === 403
            ? "Verify your email first: open the link we sent when you signed up."
            : (error.message ?? "Sign-in failed"),
      });
      return;
    }
    // refresh() re-renders server components with the new session cookie.
    router.replace("/");
    router.refresh();
  }

  return (
    <div className="grid gap-4">
      <SocialButtons providers={socialProviders} onError={setStatus} />
      <form onSubmit={onSubmit} className="grid gap-3">
        <label className={labelClass}>
          Email
          <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
        </label>
        <label className={labelClass}>
          Password
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className={inputClass}
          />
        </label>
        <Message status={status} />
        <button type="submit" disabled={pending} className={primaryButtonClass}>
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="flex justify-between text-sm">
        <Link href="/auth/forgot-password" className="underline">
          Forgot password?
        </Link>
        <Link href="/auth/sign-up" className="underline">
          Create an account
        </Link>
      </div>
    </div>
  );
}

export function SignUpForm({ socialProviders }: { socialProviders: SocialProviderInfo[] }) {
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setStatus(null);
    const form = event.currentTarget;
    const { error } = await authClient.signUp.email({
      name: field(form, "name"),
      email: field(form, "email"),
      password: field(form, "password"),
      callbackURL: "/",
    });
    setPending(false);
    if (error) {
      setStatus({ tone: "error", text: error.message ?? "Could not create the account" });
      return;
    }
    setDone(true);
  }

  if (done) {
    return (
      <Message
        status={{
          tone: "info",
          text: "Check your inbox and open the verification link to finish. (Development: the link is printed in the Next.js terminal.)",
        }}
      />
    );
  }

  return (
    <div className="grid gap-4">
      <SocialButtons providers={socialProviders} onError={setStatus} />
      <form onSubmit={onSubmit} className="grid gap-3">
        <label className={labelClass}>
          Full name
          <input id="name" name="name" autoComplete="name" required className={inputClass} />
        </label>
        <label className={labelClass}>
          Email
          <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
        </label>
        <label className={labelClass}>
          Password (12+ characters)
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            required
            className={inputClass}
          />
        </label>
        <Message status={status} />
        <button type="submit" disabled={pending} className={primaryButtonClass}>
          {pending ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/auth/sign-in" className="underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

export function ForgotPasswordForm() {
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const { error } = await authClient.requestPasswordReset({
      email: field(event.currentTarget, "email"),
      redirectTo: "/auth/reset-password",
    });
    setPending(false);
    // Same answer whether or not the account exists, so the form can't be used to discover accounts.
    setStatus(
      error && (error.status ?? 500) >= 500
        ? { tone: "error", text: error.message ?? "Could not send the email. Try again later." }
        : { tone: "info", text: "If an account exists for that email, a reset link is on its way." },
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3">
      <label className={labelClass}>
        Email
        <input id="email" name="email" type="email" autoComplete="email" required className={inputClass} />
      </label>
      <Message status={status} />
      <button type="submit" disabled={pending} className={primaryButtonClass}>
        {pending ? "Sending…" : "Send reset link"}
      </button>
      <Link href="/auth/sign-in" className="text-sm underline">
        Back to sign in
      </Link>
    </form>
  );
}

export function ResetPasswordForm({ token }: { token: string }) {
  const [status, setStatus] = useState<Status>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    const { error } = await authClient.resetPassword({ newPassword: field(event.currentTarget, "password"), token });
    setPending(false);
    if (error) {
      setStatus({ tone: "error", text: error.message ?? "This link is invalid or has expired." });
      return;
    }
    setDone(true);
  }

  if (done) {
    return (
      <div className="grid gap-3">
        <Message status={{ tone: "info", text: "Password changed. Other sessions were signed out." }} />
        <Link href="/auth/sign-in" className={primaryButtonClass}>
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-3">
      <label className={labelClass}>
        New password (12+ characters)
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={12}
          required
          className={inputClass}
        />
      </label>
      <Message status={status} />
      <button type="submit" disabled={pending} className={primaryButtonClass}>
        {pending ? "Saving…" : "Set new password"}
      </button>
    </form>
  );
}
