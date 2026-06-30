import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Card, PageTitle } from "@/components/app-shell";
import { integrations } from "@/lib/mock-data";
import { Check, Clock, AlertCircle } from "lucide-react";
import { useState } from "react";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings · DocVerify" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const [prefs, setPrefs] = useState({ email: true, inapp: true });
  const [profile, setProfile] = useState({ name: "Anita Verma", contact: "+91 90000 00000", branch: "Howeville" });

  return (
    <AppShell>
      <PageTitle title="Settings & Integrations" subtitle="Manage how you're notified and view registry integration status." />

      <div className="grid gap-5 lg:grid-cols-2 max-w-5xl">
        <Card className="p-6">
          <h3 className="text-sm font-semibold">Profile</h3>
          <p className="text-xs text-muted-foreground">Visible to your branch admin.</p>
          <div className="mt-4 space-y-3 text-sm">
            <Field label="Name">
              <input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 outline-none focus:border-primary" />
            </Field>
            <Field label="Contact">
              <input value={profile.contact} onChange={(e) => setProfile({ ...profile, contact: e.target.value })}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 outline-none focus:border-primary" />
            </Field>
            <Field label="Branch">
              <input value={profile.branch} disabled
                className="w-full rounded-lg border border-border bg-secondary px-3 py-2.5" />
            </Field>
            <button className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
              Save profile
            </button>
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-sm font-semibold">Notification preferences</h3>
          <p className="text-xs text-muted-foreground">How you want to know when an analysis is complete.</p>
          <div className="mt-4 space-y-2">
            <Toggle label="Email notifications" checked={prefs.email} onChange={(v) => setPrefs({ ...prefs, email: v })} />
            <Toggle label="In-app notifications" checked={prefs.inapp} onChange={(v) => setPrefs({ ...prefs, inapp: v })} />
          </div>

          <h3 className="mt-6 text-sm font-semibold">Model version</h3>
          <div className="mt-2 text-xs text-muted-foreground">DocVerify Risk Model v2.4 · updated 2024-11-01</div>
        </Card>

        <Card className="p-6 lg:col-span-2">
          <h3 className="text-sm font-semibold">External integrations</h3>
          <p className="text-xs text-muted-foreground">Configured at the infrastructure level; read-only here.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {integrations.map((i) => {
              const ok = i.status.startsWith("Connected");
              const pending = i.status === "Pending";
              return (
                <div key={i.name} className="flex items-center gap-3 rounded-lg border border-border p-3">
                  <div
                    className="grid size-9 place-items-center rounded-lg"
                    style={{
                      backgroundColor: ok
                        ? "color-mix(in oklab, var(--success) 15%, transparent)"
                        : pending
                        ? "color-mix(in oklab, var(--warning) 25%, transparent)"
                        : "var(--secondary)",
                      color: ok ? "var(--success)" : pending ? "oklch(0.45 0.12 75)" : "var(--muted-foreground)",
                    }}
                  >
                    {ok ? <Check className="size-4" /> : pending ? <Clock className="size-4" /> : <AlertCircle className="size-4" />}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium">{i.name}</div>
                    <div className="text-xs text-muted-foreground">{i.status} · updated {i.updated}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium">{label}</label>
      {children}
    </div>
  );
}
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button" onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-lg border border-border bg-background p-3 text-sm"
    >
      <span>{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-primary" : "bg-secondary"}`}>
        <span className={`absolute top-0.5 size-4 rounded-full bg-white transition ${checked ? "left-4" : "left-0.5"}`} />
      </span>
    </button>
  );
}