import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { AppShell, Card, PageTitle } from "@/components/app-shell";
import { useState } from "react";
import { saveCase } from "@/lib/mock-data";

export const Route = createFileRoute("/cases/new")({
  head: () => ({
    meta: [
      { title: "New Case · DocVerify" },
      { name: "description", content: "Create a new loan verification case." },
    ],
  }),
  component: NewCasePage,
});

function NewCasePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "", pan: "", aadhaar: "", dob: "", phone: "", address: "",
    loanType: "Home Loan", amount: "", branch: "Howeville",
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <AppShell>
      <PageTitle title="New Case" subtitle="Capture applicant and loan context before uploading documents." />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const dynamicCaseId = "CNB" + Math.random().toString(36).substring(2, 8).toUpperCase();
          const newCase = {
            id: dynamicCaseId,
            applicant: form.name || "Jeff Henry",
            pan: form.pan || "ABCDE1234F",
            loanType: form.loanType,
            loanAmount: Number(form.amount.replace(/,/g, "")) || 4500000,
            branch: form.branch,
            officer: "Anita Verma",
            submittedAt: new Date().toISOString().split('T')[0],
            status: "Uploading" as const,
            score: 0,
            risk: "low" as const,
            docs: [],
            anomalies: [],
            conflicts: [],
            external: [],
            hash: "N/A",
            auditId: `AL-${dynamicCaseId}`,
          };
          saveCase(newCase);
          navigate({ to: "/cases/$caseId/upload", params: { caseId: dynamicCaseId } });
        }}
        className="space-y-6 max-w-4xl"
      >
        <Card className="p-6">
          <SectionHeader title="Applicant Information" hint="Captured on the loan application." />
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Full name"><Input value={form.name} onChange={set("name")} placeholder="Jeff Henry" /></Field>
            <Field label="PAN number"><Input value={form.pan} onChange={set("pan")} placeholder="ABCDE1234F" /></Field>
            <Field label="Aadhaar (masked)"><Input value={form.aadhaar} onChange={set("aadhaar")} placeholder="XXXX XXXX 1234" /></Field>
            <Field label="Date of birth"><Input type="date" value={form.dob} onChange={set("dob")} /></Field>
            <Field label="Contact number"><Input value={form.phone} onChange={set("phone")} placeholder="+91 90000 00000" /></Field>
            <Field label="Address" className="md:col-span-2">
              <textarea
                value={form.address} onChange={set("address")} rows={2}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
              />
            </Field>
          </div>
        </Card>

        <Card className="p-6">
          <SectionHeader title="Loan Details" hint="What is being verified." />
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Loan type">
              <select
                value={form.loanType} onChange={set("loanType")}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
              >
                <option>Home Loan</option><option>Business Loan</option><option>Personal Loan</option><option>Auto Loan</option>
              </select>
            </Field>
            <Field label="Loan amount (₹)"><Input value={form.amount} onChange={set("amount")} placeholder="4,500,000" /></Field>
            <Field label="Branch">
              <select
                value={form.branch} onChange={set("branch")}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
              >
                <option>Howeville</option><option>East Nash</option><option>Gutkowski</option><option>South Lillybury</option>
              </select>
            </Field>
            <Field label="Assigned officer">
              <Input value="Anita Verma" disabled />
            </Field>
          </div>
        </Card>

        <div className="flex flex-wrap justify-between gap-3">
          <Link to="/dashboard" className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm">Back to dashboard</Link>
          <div className="flex gap-2">
            <button type="button" className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm">Save as draft</button>
            <button type="submit" className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground">
              Proceed to document upload
            </button>
          </div>
        </div>
      </form>
    </AppShell>
  );
}

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="mb-5">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-xs font-medium">{label}</label>
      {children}
    </div>
  );
}
function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary disabled:bg-secondary"
    />
  );
}