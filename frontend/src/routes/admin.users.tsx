import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Card, PageTitle } from "@/components/app-shell";
import { mockUsers } from "@/lib/mock-data";
import { UserPlus, MoreHorizontal } from "lucide-react";

export const Route = createFileRoute("/admin/users")({
  head: () => ({ meta: [{ title: "User Management · DocVerify" }] }),
  component: AdminUsersPage,
});

function AdminUsersPage() {
  return (
    <AppShell>
      <PageTitle
        title="User Management"
        subtitle="Provision and manage officer accounts. Admins do not access case-level fraud reports."
        actions={
          <button className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground">
            <UserPlus className="size-4" /> Add officer
          </button>
        }
      />

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-secondary text-secondary-foreground">
            <tr className="text-left">
              {["Name", "Employee ID", "Role", "Branch", "Status", "Last login", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-xs font-medium uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockUsers.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-4 py-3">
                  <div className="font-medium">{u.name}</div>
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{u.employeeId}</td>
                <td className="px-4 py-3">{u.role}</td>
                <td className="px-4 py-3">{u.branch}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                      u.status === "Active"
                        ? "bg-[var(--success)]/15 text-[var(--success)]"
                        : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {u.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{u.lastLogin}</td>
                <td className="px-4 py-3 text-right">
                  <button className="grid size-8 place-items-center rounded-lg border border-border hover:bg-secondary">
                    <MoreHorizontal className="size-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </AppShell>
  );
}