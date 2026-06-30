import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, Card, PageTitle, RiskPill, StatusPill } from "@/components/app-shell";
import { mockCases } from "@/lib/mock-data";
import { Search, Plus, Filter, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard · DocVerify" },
      { name: "description", content: "Active and historical loan verification cases at a glance." },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const stats = useMemo(() => {
    const today = mockCases.length;
    const pending = mockCases.filter((c) => c.status === "Ready for Review" || c.status === "Processing").length;
    const highRisk = mockCases.filter((c) => c.risk === "high" || c.risk === "critical").length;
    const cleared = mockCases.filter((c) => c.decision?.type === "Approved").length;
    return { today, pending, highRisk, cleared };
  }, []);

  const filtered = mockCases.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    if (!q) return true;
    const t = q.toLowerCase();
    return c.applicant.toLowerCase().includes(t) || c.id.toLowerCase().includes(t);
  });

  return (
    <AppShell>
      <PageTitle
        title="Good morning, Anita"
        subtitle="Here's where your queue stands today."
        actions={
          <Link
            to="/cases/new"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-95"
          >
            <Plus className="size-4" /> New case
          </Link>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <StatCard label="Cases today" value={stats.today} hint="+2 vs yesterday" />
        <StatCard label="Pending review" value={stats.pending} hint="Avg wait 14 min" tone="info" />
        <StatCard label="High risk" value={stats.highRisk} hint="Needs senior review" tone="danger" />
        <StatCard label="Cleared" value={stats.cleared} hint="This week" tone="success" />
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-border bg-background px-3 py-2">
            <Search className="size-4 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by applicant or case ID"
              className="w-full bg-transparent text-sm outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
              <Filter className="size-4 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-transparent text-sm outline-none"
              >
                <option value="all">All statuses</option>
                <option>Processing</option>
                <option>Ready for Review</option>
                <option>Decision Recorded</option>
              </select>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary text-secondary-foreground">
              <tr className="text-left">
                {["Case ID", "Applicant", "Loan", "Submitted", "Docs", "Status", "Risk", "Action"].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs font-medium uppercase tracking-wide">
                    <span className="inline-flex items-center gap-1">
                      {h}
                      <ArrowUpDown className="size-3 opacity-50" />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => {
                const target =
                  c.status === "Decision Recorded"
                    ? `/cases/${c.id}`
                    : c.status === "Processing"
                    ? `/cases/${c.id}/analyzing`
                    : `/cases/${c.id}/report`;
                return (
                  <tr key={c.id} className="border-t border-border hover:bg-secondary/40">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">#{c.id}</td>
                    <td className="px-4 py-3 font-medium">{c.applicant}</td>
                    <td className="px-4 py-3">
                      <div>{c.loanType}</div>
                      <div className="text-xs text-muted-foreground">₹{c.loanAmount.toLocaleString("en-IN")}</div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{c.submittedAt}</td>
                    <td className="px-4 py-3">{c.docs.length}</td>
                    <td className="px-4 py-3"><StatusPill status={c.status} /></td>
                    <td className="px-4 py-3">
                      {c.status === "Processing" ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : (
                        <RiskPill level={c.risk} score={c.score} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={target}
                        className="text-xs font-medium text-primary hover:underline"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <div>Showing {filtered.length} of {mockCases.length}</div>
          <div className="flex gap-1">
            <button className="rounded-md border border-border px-2.5 py-1">Prev</button>
            <button className="rounded-md border border-border bg-primary px-2.5 py-1 text-primary-foreground">1</button>
            <button className="rounded-md border border-border px-2.5 py-1">2</button>
            <button className="rounded-md border border-border px-2.5 py-1">Next</button>
          </div>
        </div>
      </Card>
    </AppShell>
  );
}

function StatCard({
  label, value, hint, tone = "default",
}: { label: string; value: number; hint: string; tone?: "default" | "info" | "danger" | "success" }) {
  const toneCls = {
    default: "text-foreground",
    info: "text-[var(--info)]",
    danger: "text-[var(--risk-high)]",
    success: "text-[var(--success)]",
  }[tone];
  return (
    <Card className="p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`mt-2 text-3xl font-semibold ${toneCls}`}>{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
    </Card>
  );
}