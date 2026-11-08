import { Suspense } from "react";
import { connection } from "next/server";
import { Badge, Card, Shell, formatDate } from "@/components/ui";
import { UserNav } from "@/components/user-nav";
import { auth } from "@/lib/auth";
import { getAdminViewer, requireViewer } from "@/lib/dal";
import { prisma } from "@/lib/db";
import { PortalButton, RoleForm, StatusForm } from "./forms";

async function AdminBoard() {
  await connection();
  await requireViewer();
  const viewer = await getAdminViewer();
  if (!viewer) {
    return (
      <Card title="Access denied">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          The admin board needs the <b>admin</b> role. Ask an administrator to promote you.
        </p>
      </Card>
    );
  }

  const [users, events] = await Promise.all([
    prisma.user.findMany({ orderBy: { createdAt: "desc" }, take: 100 }),
    prisma.auditEvent.findMany({ orderBy: { occurredAt: "desc" }, take: 30 }),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <Card title={`Users (${users.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-500">
              <tr>
                <th className="py-2 pr-4">User</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Last sign-in</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2">Access</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === viewer.user.id;
                return (
                  <tr key={u.id} className="border-t border-zinc-100 align-top dark:border-zinc-800">
                    <td className="py-2 pr-4">
                      <div className="font-medium">{u.fullName ?? "—"}</div>
                      <div className="text-xs text-zinc-500">{u.email}</div>
                      {isSelf && <div className="text-xs text-zinc-400">(you)</div>}
                    </td>
                    <td className="py-2 pr-4">
                      {u.isActive ? <Badge tone="ok">active</Badge> : <Badge tone="bad">suspended</Badge>}
                    </td>
                    <td className="py-2 pr-4 text-xs">{formatDate(u.lastLoginAt)}</td>
                    <td className="py-2 pr-4">
                      <RoleForm userId={u.id} role={u.role} disabled={isSelf} />
                    </td>
                    <td className="py-2">
                      <StatusForm userId={u.id} isActive={u.isActive} disabled={isSelf} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {auth.features.adminPortal && (
        <Card title="Company SSO (WorkOS Admin Portal)">
          <p className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
            Opens a one-time WorkOS page where your IT admin connects Microsoft Entra ID and verifies the
            company domain. After that, <code>@innowhyte.com</code> users are sent to Microsoft automatically.
          </p>
          <div className="flex flex-wrap gap-2">
            <PortalButton intent="domain_verification" label="1. Verify company domain" />
            <PortalButton intent="sso" label="2. Set up Microsoft Entra SSO" />
          </div>
        </Card>
      )}

      <Card title="Audit trail (latest 30, append-only)">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="uppercase text-zinc-500">
              <tr>
                <th className="py-2 pr-3">When</th>
                <th className="py-2 pr-3">Action</th>
                <th className="py-2 pr-3">Outcome</th>
                <th className="py-2 pr-3">Actor</th>
                <th className="py-2 pr-3">Details</th>
                <th className="py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-t border-zinc-100 align-top dark:border-zinc-800">
                  <td className="py-1.5 pr-3 whitespace-nowrap">{formatDate(e.occurredAt)}</td>
                  <td className="py-1.5 pr-3 font-mono">{e.action}</td>
                  <td className="py-1.5 pr-3">
                    <Badge tone={e.outcome === "success" ? "ok" : e.outcome === "denied" ? "warn" : "bad"}>
                      {e.outcome}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-3">{e.actorEmail ?? e.actorExternalId ?? "—"}</td>
                  <td className="py-1.5 pr-3 font-mono text-zinc-500">{JSON.stringify(e.details)}</td>
                  <td className="py-1.5">{e.ipAddress ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export default function AdminPage() {
  return (
    <Shell
      nav={
        <Suspense fallback={null}>
          <UserNav />
        </Suspense>
      }
    >
      <h1 className="mb-6 text-xl font-semibold">Admin board</h1>
      <Suspense fallback={<p className="text-sm text-zinc-500">Loading…</p>}>
        <AdminBoard />
      </Suspense>
    </Shell>
  );
}
