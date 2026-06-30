import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell, Card, PageTitle, RiskPill } from "@/components/app-shell";
import { mockCases } from "@/lib/mock-data";
import { Search, Download } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/audit")({
  head: () => ({ meta: [{ title: "Audit Trail · DocVerify" }] }),
  component: AuditPage,
});

function AuditPage() {
  const [q, setQ] = useState("");
  const entries = mockCases.filter((c) => {
    if (!q) return true;
    const t = q.toLowerCase();
    return c.applicant.toLowerCase().includes(t) || c.id.toLowerCase().includes(t) || c.officer.toLowerCase().includes(t);
  });

  return (
    <AppShell>
      <PageTitle
        title="Audit Trail"
        subtitle="Tamper-evident log of every verification run."
        actions={
          <div className="flex gap-2">
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
              <Download className="size-4" /> Export CSV
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
              <Download className="size-4" /> Export PDF
            </button>
          </div>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <div className="flex flex-1 min-w-[240px] items-center gap-2 rounded-lg border border-border bg-background px-3 py-2">
            <Search className="size-4 text-muted-foreground" />
            <input
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search by case, applicant or officer"
              className="w-full bg-transparent text-sm outline-none"
            />
          </div>
          <select className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
            <option>All risk levels</option><option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
          </select>
          <select className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
            <option>All decisions</option><option>Approved</option><option>Rejected</option><option>Escalated</option>
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary text-secondary-foreground">
              <tr className="text-left">
                {["Case", "Applicant", "Processed", "Score", "Decision", "Officer", "Hash", "Log ID"].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs font-medium uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((c) => (
                <tr key={c.id} className="border-t border-border hover:bg-secondary/40">
                  <td className="px-4 py-3">
                    <Link to="/cases/$caseId" params={{ caseId: c.id }} className="font-mono text-xs text-primary hover:underline">
                      #{c.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium">{c.applicant}</td>
                  <td className="px-4 py-3 text-muted-foreground">{c.submittedAt}</td>
                  <td className="px-4 py-3">
                    {c.status === "Processing" ? <span className="text-muted-foreground">—</span> : <RiskPill level={c.risk} score={c.score} />}
                  </td>
                  <td className="px-4 py-3">{c.decision?.type ?? <span className="text-muted-foreground">Pending</span>}</td>
                  <td className="px-4 py-3">{c.officer}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.hash}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.auditId}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}