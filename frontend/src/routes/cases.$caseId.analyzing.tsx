import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { AppShell, Card } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, saveCase } from "@/lib/mock-data";
import { Check, Loader2, Circle } from "lucide-react";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/cases/$caseId/analyzing")({
  head: () => ({ meta: [{ title: "Analyzing · DocVerify" }] }),
  component: AnalyzingPage,
});

const steps = [
  "Document Ingestion & OCR",
  "Tamper & Metadata Forensics",
  "Visual Forgery Analysis",
  "Cross-Document Consistency Check",
  "External Registry Correlation",
  "Risk Score Computation",
];

function AnalyzingPage() {
  const { caseId } = useParams({ from: "/cases/$caseId/analyzing" });
  const c = getCase(caseId);
  const navigate = useNavigate();
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    if (c && c.status !== "Processing" && stepIdx === 0) {
      c.status = "Processing";
      saveCase(c);
    }
  }, [c, stepIdx]);

  useEffect(() => {
    if (stepIdx >= steps.length) {
      if (c && c.status !== "Ready for Review" && c.status !== "Decision Recorded") {
        c.status = "Ready for Review";
        saveCase(c);
      }
      const t = setTimeout(() => navigate({ to: "/cases/$caseId/report", params: { caseId } }), 700);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStepIdx((s) => s + 1), 1100);
    return () => clearTimeout(t);
  }, [stepIdx, navigate, caseId, c]);

  const remaining = Math.max(0, (steps.length - stepIdx) * 12);

  return (
    <AppShell>
      <CaseBar applicant={c?.applicant ?? "Applicant"} caseId={caseId} amount={c?.loanAmount ?? 0} />
      <Card className="p-8 max-w-3xl mx-auto">
        <div className="text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-full bg-primary-soft">
            <Loader2 className="size-7 animate-spin text-primary" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Analyzing {c?.docs.length ?? 5} documents</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Results ready in ~{remaining}s. You can leave this screen — we'll continue in the background.
          </p>
        </div>

        <div className="mt-8 space-y-2">
          {steps.map((s, i) => {
            const state = i < stepIdx ? "done" : i === stepIdx ? "active" : "pending";
            return (
              <div
                key={s}
                className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${
                  state === "active" ? "border-primary bg-primary-soft" : "border-border bg-background"
                }`}
              >
                {state === "done" && (
                  <div className="grid size-7 place-items-center rounded-full bg-[var(--success)] text-white">
                    <Check className="size-4" />
                  </div>
                )}
                {state === "active" && (
                  <div className="grid size-7 place-items-center rounded-full bg-primary text-primary-foreground">
                    <Loader2 className="size-4 animate-spin" />
                  </div>
                )}
                {state === "pending" && (
                  <div className="grid size-7 place-items-center rounded-full bg-secondary text-muted-foreground">
                    <Circle className="size-3" />
                  </div>
                )}
                <div className="text-sm font-medium">{s}</div>
                <div className="ml-auto text-xs text-muted-foreground capitalize">{state}</div>
              </div>
            );
          })}
        </div>

        <div className="mt-8 text-center">
          <Link to="/dashboard" className="text-sm text-primary hover:underline">
            Return to dashboard — we'll notify you
          </Link>
        </div>
      </Card>
    </AppShell>
  );
}