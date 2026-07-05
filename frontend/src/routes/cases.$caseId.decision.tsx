import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { AppShell, Card, RiskPill } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, saveCase, type Decision } from "@/lib/mock-data";
import { Sparkles, ChevronLeft } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/cases/$caseId/decision")({
  head: () => ({ meta: [{ title: "Decision · DocVerify" }] }),
  component: DecisionPage,
});

const options: { id: Decision; label: string; tone: string; needsNotes?: boolean }[] = [
  { id: "Approved", label: "Approve · low risk, proceed with loan", tone: "var(--success)" },
  { id: "Approved with Conditions", label: "Approve with conditions (e.g., video KYC, extra document)", tone: "var(--info)", needsNotes: true },
  { id: "Escalated", label: "Escalate for senior review", tone: "var(--warning)" },
  { id: "Rejected", label: "Reject · document fraud suspected", tone: "var(--risk-high)", needsNotes: true },
  { id: "Resubmission Requested", label: "Request re-submission of specific documents", tone: "var(--primary)", needsNotes: true },
];

function DecisionPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/decision" });
  const c = getCase(caseId);
  const navigate = useNavigate();
  const [choice, setChoice] = useState<Decision | null>(null);
  const [notes, setNotes] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  if (!c) return <AppShell><div>Case not found.</div></AppShell>;

  const needsNotes = options.find((o) => o.id === choice)?.needsNotes ?? false;
  const canSubmit = choice && confirmed && (!needsNotes || notes.trim().length > 4);

  return (
    <AppShell>
      <CaseBar applicant={c.applicant} caseId={c.id} amount={c.loanAmount} />
      <div className="mb-4">
        <Link to="/cases/$caseId/report" params={{ caseId }} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
          <ChevronLeft className="size-3.5" /> Back to report
        </Link>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px] max-w-5xl">
        <Card className="p-6 space-y-5">
          <div className="rounded-lg bg-primary-soft p-4">
            <div className="flex items-center gap-2 text-xs font-medium text-[var(--accent-foreground)]">
              <Sparkles className="size-4" /> System recommends
            </div>
            <div className="mt-1 text-sm">Video KYC before any approval — signature mismatch detected.</div>
          </div>

          <div>
            <h3 className="mb-3 text-sm font-semibold">Select decision</h3>
            <div className="space-y-2">
              {options.map((o) => (
                <label
                  key={o.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm ${
                    choice === o.id ? "border-primary bg-primary-soft" : "border-border bg-background"
                  }`}
                >
                  <input
                    type="radio" name="decision" className="mt-1 accent-[var(--primary)]"
                    checked={choice === o.id}
                    onChange={() => setChoice(o.id)}
                  />
                  <div className="flex-1">
                    <div className="font-medium" style={{ color: choice === o.id ? "var(--accent-foreground)" : undefined }}>
                      {o.id}
                    </div>
                    <div className="text-xs text-muted-foreground">{o.label}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium">
              Conditions / notes {needsNotes && <span className="text-destructive">*</span>}
            </label>
            <textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={needsNotes ? "Specify conditions or reasons…" : "Optional notes for the record."}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </div>

          <label className="flex items-start gap-2 text-xs">
            <input
              type="checkbox" className="mt-0.5 accent-[var(--primary)]"
              checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span>
              I confirm this decision is based on my professional review of the analysis and supporting documents.
            </span>
          </label>

          <div className="flex justify-end gap-2">
            <Link to="/cases/$caseId/report" params={{ caseId }} className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm">
              Review report again
            </Link>
            <button
              disabled={!canSubmit}
              onClick={() => {
                if (c) {
                  c.decision = {
                    type: choice!,
                    notes: notes,
                    by: "Anita Verma",
                    at: new Date().toISOString().slice(0, 16).replace("T", " ")
                  };
                  c.status = "Decision Recorded";
                  saveCase(c);
                }
                navigate({ to: "/cases/$caseId", params: { caseId } });
              }}
              className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 cursor-pointer"
            >
              Submit decision
            </button>
          </div>
        </Card>

        <Card className="p-6 h-fit">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Analysis snapshot
          </div>
          <div className="mt-2 text-4xl font-semibold" style={{ color: `var(--risk-${c.risk})` }}>
            {c.score}
          </div>
          <div className="mt-1"><RiskPill level={c.risk} /></div>
          <div className="mt-4 space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-muted-foreground">Documents</span><span>{c.docs.length}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Insights</span><span>{c.anomalies.length}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Conflicts</span><span>{c.conflicts.length}</span></div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}