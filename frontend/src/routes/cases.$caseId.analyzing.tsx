import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { AppShell, Card } from "@/components/app-shell";
import { CaseBar } from "./cases.$caseId.upload";
import { getCase, saveCase, applyCaseResult } from "@/lib/mock-data";
import { analyzeCase, ApiError } from "@/lib/api";
import { Check, Loader2, Circle, AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const started = useRef(false);

  // Kick off the real analysis exactly once.
  useEffect(() => {
    if (started.current) return;
    started.current = true;

    if (c && c.status !== "Processing") {
      c.status = "Processing";
      saveCase(c);
    }

    analyzeCase(caseId)
      .then((result) => {
        applyCaseResult(caseId, result);
        setDone(true);
        setStepIdx(steps.length);
        setTimeout(() => navigate({ to: "/cases/$caseId/report", params: { caseId } }), 600);
      })
      .catch((err) => setError(err));
  }, [caseId, c, navigate]);

  // Cosmetic progress: advance through the stages while the request is in
  // flight, but hold on the last stage until the real result lands.
  useEffect(() => {
    if (error || done) return;
    if (stepIdx >= steps.length - 1) return;
    const t = setTimeout(() => setStepIdx((s) => Math.min(s + 1, steps.length - 1)), 1100);
    return () => clearTimeout(t);
  }, [stepIdx, error, done]);

  if (error) {
    const detail =
      error instanceof ApiError
        ? typeof error.detail === "string"
          ? error.detail
          : JSON.stringify(error.detail)
        : error instanceof Error
        ? error.message
        : "Analysis failed.";
    return (
      <AppShell>
        <CaseBar applicant={c?.applicant ?? "Applicant"} caseId={caseId} amount={c?.loanAmount ?? 0} />
        <Card className="p-8 max-w-3xl mx-auto text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-full bg-destructive/10">
            <AlertTriangle className="size-7 text-destructive" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Analysis could not complete</h2>
          <p className="mt-2 text-sm text-muted-foreground break-words">{detail}</p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              to="/cases/$caseId/upload"
              params={{ caseId }}
              className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm"
            >
              Back to upload
            </Link>
            <Link to="/dashboard" className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground">
              Return to dashboard
            </Link>
          </div>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <CaseBar applicant={c?.applicant ?? "Applicant"} caseId={caseId} amount={c?.loanAmount ?? 0} />
      <Card className="p-8 max-w-3xl mx-auto">
        <div className="text-center">
          <div className="mx-auto grid size-16 place-items-center rounded-full bg-primary-soft">
            <Loader2 className="size-7 animate-spin text-primary" />
          </div>
          <h2 className="mt-5 text-xl font-semibold">Analyzing {c?.docs.length ?? ""} documents</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Running the real detection pipeline across the security and model services. This can take a moment.
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
