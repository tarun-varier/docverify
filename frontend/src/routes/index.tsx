import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ShieldAlert, ArrowRight } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "DocVerify · Secure Sign In" },
      { name: "description", content: "AI-powered document verification for smarter underwriting." },
      { property: "og:title", content: "DocVerify · Secure Sign In" },
      { property: "og:description", content: "AI-powered document verification for smarter underwriting." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [employeeId, setEmployeeId] = useState("EMP-1042");
  const [password, setPassword] = useState("••••••••");

  return (
    <div className="grid min-h-screen lg:grid-cols-2 bg-background">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-sidebar text-sidebar-foreground">
        <div className="flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
            <ShieldAlert className="size-5" />
          </div>
          <div>
            <div className="text-base font-semibold">DocVerify</div>
            <div className="text-xs opacity-80">Underwriting Suite</div>
          </div>
        </div>
        <div className="max-w-md space-y-4">
          <h2 className="text-3xl font-semibold leading-tight">
            AI-powered document verification for smarter underwriting.
          </h2>
          <p className="text-sm opacity-85">
            Cross-document analysis, tamper forensics and registry correlation —
            so your team approves the right loans, faster.
          </p>
        </div>
        <div className="text-xs opacity-75">© 2026 DocVerify · Bank-grade security</div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12">
        <form
          className="w-full max-w-sm space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            navigate({ to: "/dashboard" });
          }}
        >
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Sign in with your bank-issued credentials.
            </p>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">Employee ID or email</label>
            <input
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-foreground">Password</label>
              <Link to="/" className="text-xs text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </div>
          <button
            type="submit"
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-95"
          >
            Sign in
            <ArrowRight className="size-4" />
          </button>
          <p className="text-center text-xs text-muted-foreground">
            Accounts are provisioned by your administrator.
          </p>
        </form>
      </div>
    </div>
  );
}
