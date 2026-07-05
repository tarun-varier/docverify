import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { AppShell, Card, RiskPill } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, type Anomaly } from "@/lib/mock-data";
import {
  AlertTriangle, FileText, Download, ChevronRight, Check, X as XIcon, MinusCircle, ShieldQuestion,
} from "lucide-react";

export const Route = createFileRoute("/cases/$caseId/report")({
  head: () => ({ meta: [{ title: "Analysis Report · DocVerify" }] }),
  component: ReportPage,
});

const sevOrder = { critical: 0, high: 1, medium: 2, low: 3 } as const;

function ReportPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/report" });
  const c = getCase(caseId);
  if (!c) return <AppShell><div>Case not found.</div></AppShell>;

  const sortedAnomalies = [...c.anomalies].sort((a, b) => sevOrder[a.severity] - sevOrder[b.severity]);

  return (
    <AppShell>
      <CaseBar
        applicant={c.applicant}
        caseId={c.id}
        amount={c.loanAmount}
        extra={
          <div className="flex gap-2">
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <Download className="size-3.5" /> Download PDF
            </button>
            <Link
              to="/cases/$caseId/decision"
              params={{ caseId }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Record decision <ChevronRight className="size-4" />
            </Link>
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Overall Fraud Confidence
              </div>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="text-5xl font-semibold" style={{ color: `var(--risk-${c.risk})` }}>{c.score}</span>
                <span className="text-sm text-muted-foreground">/ 100</span>
                <RiskPill level={c.risk} />
              </div>
              <p className="mt-2 text-sm text-muted-foreground max-w-md">
                {c.risk === "low"
                  ? "Documents look consistent. Routine approval likely."
                  : c.risk === "medium"
                  ? "Some anomalies detected. Senior review or KYC may be warranted."
                  : "Significant fraud indicators. Escalation strongly recommended."}
              </p>
            </div>
            <ScoreDial score={c.score} risk={c.risk} />
          </div>
        </Card>

        <Card className="p-6">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            System Recommendation
          </div>
          <div className="mt-2 text-base font-semibold">
            {c.score >= 80 
              ? "Reject loan application" 
              : c.score >= 50 
              ? "Escalate for senior review" 
              : "Proceed with approval"}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {c.score >= 80 
              ? "Severe fraud risk and tamper flags detected. Immediate block recommended." 
              : c.score >= 50 
              ? "Multiple document anomalies detected. Recommend video KYC before approval." 
              : "All document structures are clean and verified."}
          </p>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-secondary px-2.5 py-1">{c.docs.length} documents</span>
            <span className="rounded-full bg-secondary px-2.5 py-1">{c.anomalies.length} insights</span>
            <span className="rounded-full bg-secondary px-2.5 py-1">{c.conflicts.length} conflicts</span>
          </div>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <SectionTitle title="Intelligent Insights" hint="Sorted by severity" />
          <div className="space-y-3">
            {sortedAnomalies.map((a) => (
              <InsightRow key={a.id} a={a} />
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <SectionTitle title="External Correlation" hint="Registry & format checks" />
          <ul className="space-y-3">
            {c.external.map((e) => (
              <li key={e.check} className="flex items-start gap-3 rounded-lg border border-border p-3">
                {e.status === "passed" && <Check className="mt-0.5 size-4 text-[var(--success)]" />}
                {e.status === "failed" && <XIcon className="mt-0.5 size-4 text-[var(--risk-high)]" />}
                {e.status === "inconclusive" && <MinusCircle className="mt-0.5 size-4 text-muted-foreground" />}
                <div>
                  <div className="text-sm font-medium">{e.check}</div>
                  <div className="text-xs text-muted-foreground">{e.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card className="p-6 lg:col-span-2">
          <SectionTitle title="Per-Document Results" hint={`${c.docs.length} files analyzed`} />
          <div className="space-y-2">
            {c.docs.map((d) => {
              const r = d.subScore >= 60 ? "high" : d.subScore >= 35 ? "medium" : "low";
              return (
                <div key={d.id} className="flex items-center gap-4 rounded-lg border border-border p-3">
                  <FileText className="size-5 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{d.name}</div>
                    <div className="text-xs text-muted-foreground line-clamp-1">{d.summary}</div>
                  </div>
                  <RiskPill level={r as never} score={d.subScore} />
                  <Link
                    to="/cases/$caseId/document/$docId"
                    params={{ caseId: c.id, docId: d.id }}
                    className="rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-secondary"
                  >
                    View document
                  </Link>
                </div>
              );
            })}
          </div>
        </Card>

        <Card className="p-6">
          <SectionTitle title="Cross-Document Conflicts" hint="Contradictions detected" />
          <div className="space-y-3">
            {c.conflicts.map((conf) => (
              <div key={conf.id} className="rounded-lg border border-border p-3">
                <div className="flex items-start gap-2">
                  <ShieldQuestion className="mt-0.5 size-4 text-[var(--risk-high)]" />
                  <div className="text-sm">{conf.description}</div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {conf.documentIds.map((id) => {
                    const d = c.docs.find((x) => x.id === id);
                    return d ? (
                      <Link
                        key={id}
                        to="/cases/$caseId/document/$docId"
                        params={{ caseId: c.id, docId: id }}
                        className="rounded-full bg-secondary px-2 py-0.5 text-[11px] hover:bg-primary-soft"
                      >
                        {d.name}
                      </Link>
                    ) : null;
                  })}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function InsightRow({ a }: { a: Anomaly }) {
  return (
    <details className="group rounded-lg border border-border bg-background open:bg-secondary/50">
      <summary className="flex cursor-pointer list-none items-start gap-3 p-4">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" style={{ color: `var(--risk-${a.severity})` }} />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{a.title}</div>
          <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
            <span className="rounded-full bg-secondary px-2 py-0.5">{a.category}</span>
            <RiskPill level={a.severity} />
          </div>
        </div>
        <ChevronRight className="mt-1 size-4 transition group-open:rotate-90" />
      </summary>
      <div className="border-t border-border px-4 py-3 text-sm text-muted-foreground">{a.detail}</div>
    </details>
  );
}

function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between">
      <h3 className="text-base font-semibold">{title}</h3>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function ScoreDial({ score, risk }: { score: number; risk: "low" | "medium" | "high" | "critical" }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const dash = (score / 100) * c;
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="var(--secondary)" strokeWidth="14" />
      <circle
        cx="70" cy="70" r={r} fill="none" stroke={`var(--risk-${risk})`} strokeWidth="14"
        strokeDasharray={`${dash} ${c}`} strokeLinecap="round" transform="rotate(-90 70 70)"
      />
      <text x="70" y="76" textAnchor="middle" className="fill-foreground" style={{ fontSize: 22, fontWeight: 600 }}>
        {score}
      </text>
    </svg>
  );
}