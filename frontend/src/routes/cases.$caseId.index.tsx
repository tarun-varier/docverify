import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { AppShell, Card, RiskPill } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase } from "@/lib/mock-data";
import { Download, Flag, ShieldCheck, FileText } from "lucide-react";

export const Route = createFileRoute("/cases/$caseId/")({
  head: () => ({ meta: [{ title: "Case Summary · DocVerify" }] }),
  component: CaseSummaryPage,
});

function CaseSummaryPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/" });
  const c = getCase(caseId);
  if (!c) return <AppShell><div>Case not found.</div></AppShell>;
  const decision = c.decision ?? { type: "Approved", notes: "Demo: decision recorded just now.", by: "Anita Verma", at: new Date().toISOString().slice(0, 16).replace("T", " ") };

  return (
    <AppShell>
      <CaseBar
        applicant={c.applicant}
        caseId={c.id}
        amount={c.loanAmount}
        extra={
          <div className="flex gap-2">
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <Flag className="size-3.5" /> Flag for compliance
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <Download className="size-3.5" /> Download report
            </button>
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Decision recorded</div>
              <div className="mt-1 text-2xl font-semibold">{decision.type}</div>
              <div className="mt-1 text-xs text-muted-foreground">By {decision.by} · {decision.at}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground">Final fraud score</div>
              <div className="text-3xl font-semibold" style={{ color: `var(--risk-${c.risk})` }}>{c.score}</div>
              <RiskPill level={c.risk} />
            </div>
          </div>
          {decision.notes && (
            <div className="mt-4 rounded-lg bg-secondary p-3 text-sm">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Officer notes</div>
              <div className="mt-1">{decision.notes}</div>
            </div>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <ShieldCheck className="size-4" /> Tamper-evident record
          </div>
          <dl className="mt-3 space-y-1.5 text-xs">
            <div className="flex justify-between"><dt className="text-muted-foreground">Document hash</dt><dd className="font-mono">{c.hash}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Audit log ID</dt><dd className="font-mono">{c.auditId}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Recorded</dt><dd>{decision.at}</dd></div>
          </dl>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <h3 className="mb-4 text-sm font-semibold">Applicant & Loan</h3>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Info label="Applicant" value={c.applicant} />
            <Info label="PAN" value={c.pan} />
            <Info label="Loan type" value={c.loanType} />
            <Info label="Amount" value={`₹${c.loanAmount.toLocaleString("en-IN")}`} />
            <Info label="Branch" value={c.branch} />
            <Info label="Officer" value={c.officer} />
            <Info label="Submitted" value={c.submittedAt} />
            <Info label="Case ID" value={c.id} />
          </dl>
        </Card>

        <Card className="p-6">
          <h3 className="mb-4 text-sm font-semibold">Documents & sub-scores</h3>
          <div className="space-y-2">
            {c.docs.map((d) => {
              const r = d.subScore >= 60 ? "high" : d.subScore >= 35 ? "medium" : "low";
              return (
                <Link
                  key={d.id}
                  to="/cases/$caseId/document/$docId" params={{ caseId: c.id, docId: d.id }}
                  className="flex items-center gap-3 rounded-lg border border-border p-2.5 hover:bg-secondary"
                >
                  <FileText className="size-4 text-primary" />
                  <div className="min-w-0 flex-1 truncate text-sm">{d.name}</div>
                  <RiskPill level={r as never} score={d.subScore} />
                </Link>
              );
            })}
          </div>
        </Card>
      </div>

      <Card className="mt-5 p-6">
        <h3 className="mb-4 text-sm font-semibold">All insights from analysis</h3>
        <ul className="space-y-2">
          {c.anomalies.map((a) => (
            <li key={a.id} className="flex items-start gap-3 rounded-lg border border-border p-3 text-sm">
              <span
                className="mt-1.5 size-2 rounded-full shrink-0"
                style={{ backgroundColor: `var(--risk-${a.severity})` }}
              />
              <div className="flex-1">
                <div className="font-medium">{a.title}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">{a.category} · {a.detail}</div>
              </div>
              <RiskPill level={a.severity} />
            </li>
          ))}
        </ul>
      </Card>
    </AppShell>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}