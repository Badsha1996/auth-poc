"use client";

import { useActionState } from "react";
import { buttonClass } from "@/components/ui";
import {
  changeRoleAction,
  openAdminPortalAction,
  setStatusAction,
  type ActionState,
} from "./actions";

function Feedback({ state }: { state: ActionState }) {
  if (!state) return null;
  return (
    <p role="status" className={`mt-1 text-xs ${state.ok ? "text-emerald-600" : "text-red-600"}`}>
      {state.message}
    </p>
  );
}

export function RoleForm({ userId, role, disabled }: { userId: string; role: string; disabled: boolean }) {
  const [state, action, pending] = useActionState(changeRoleAction, null);
  return (
    <form action={action}>
      <input type="hidden" name="userId" value={userId} />
      <div className="flex gap-1">
        <select
          name="role"
          defaultValue={role}
          disabled={disabled || pending}
          aria-label="Role"
          className="rounded-md border border-zinc-300 bg-transparent px-2 py-1 text-sm dark:border-zinc-700"
        >
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" disabled={disabled || pending} className={buttonClass}>
          {pending ? "Saving…" : "Save"}
        </button>
      </div>
      <Feedback state={state} />
    </form>
  );
}

export function StatusForm({ userId, isActive, disabled }: { userId: string; isActive: boolean; disabled: boolean }) {
  const [state, action, pending] = useActionState(setStatusAction, null);
  return (
    <form action={action}>
      <input type="hidden" name="userId" value={userId} />
      <input type="hidden" name="isActive" value={isActive ? "false" : "true"} />
      <button type="submit" disabled={disabled || pending} className={buttonClass}>
        {pending ? "…" : isActive ? "Suspend" : "Restore"}
      </button>
      <Feedback state={state} />
    </form>
  );
}

export function PortalButton({ intent, label }: { intent: "sso" | "domain_verification"; label: string }) {
  const [state, action, pending] = useActionState(openAdminPortalAction, null);
  return (
    <form action={action}>
      <input type="hidden" name="intent" value={intent} />
      <button type="submit" disabled={pending} className={buttonClass}>
        {pending ? "Opening…" : label}
      </button>
      <Feedback state={state} />
    </form>
  );
}
