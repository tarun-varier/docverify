import { Link, useRouter, type LinkProps } from "@tanstack/react-router";
import {
  LayoutDashboard,
  FolderSearch,
  ShieldCheck,
  Settings,
  Users,
  Bell,
  LogOut,
  ShieldAlert,
} from "lucide-react";
import type { ReactNode } from "react";
import canaraLogo from "@/assets/canara-bank-logo.png";

interface NavItem {
  to: LinkProps["to"];
  label: string;
  Icon: typeof LayoutDashboard;
}

const navItems: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { to: "/cases/new", label: "New Case", Icon: FolderSearch },
  { to: "/audit", label: "Audit Trail", Icon: ShieldCheck },
  { to: "/admin/users", label: "Admin", Icon: Users },
  { to: "/settings", label: "Settings", Icon: Settings },
];

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = router.state.location.pathname;

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden md:flex md:w-60 flex-col bg-sidebar text-sidebar-foreground">
        <div className="flex items-center gap-2 px-6 py-6">
          <div className="grid size-9 place-items-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
            <ShieldAlert className="size-5" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight">DocVerify</div>
            <div className="text-[11px] opacity-75 leading-tight">Underwriting Suite</div>
          </div>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {navItems.map(({ to, label, Icon }) => {
            const active = path === to || (to !== "/dashboard" && path.startsWith(String(to)));
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  active
                    ? "bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                    : "hover:bg-sidebar-accent"
                }`}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <Link
          to="/"
          className="m-3 flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm hover:bg-sidebar-accent"
        >
          <LogOut className="size-4" />
          Log out
        </Link>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
          <div className="flex items-center gap-3">
            <div
              className="grid h-9 w-[168px] place-items-center rounded-lg bg-surface"
              aria-label="Canara Bank"
              title="Canara Bank"
            >
              <img
                src={canaraLogo}
                alt="Canara Bank"
                className="h-7 w-auto select-none"
                draggable={false}
              />
            </div>
            <div className="leading-tight">
              <div className="text-[11px] text-muted-foreground">Doc Verify · {pageLabel(path)}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              aria-label="Notifications"
              className="relative grid size-9 place-items-center rounded-lg border border-border bg-surface hover:bg-secondary"
            >
              <Bell className="size-4" />
              <span className="absolute right-2 top-2 size-1.5 rounded-full bg-destructive" />
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5">
              <div className="grid size-7 place-items-center rounded-full bg-primary text-primary-foreground text-xs font-semibold">
                AV
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-xs font-semibold leading-tight">Anita Verma</div>
                <div className="text-[11px] text-muted-foreground leading-tight">Underwriter · Howeville</div>
              </div>
            </div>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

function pageLabel(path: string): string {
  if (path.startsWith("/dashboard")) return "Dashboard";
  if (path.startsWith("/cases/new")) return "New Case";
  if (path.includes("/document/")) return "Document Viewer";
  if (path.includes("/decision")) return "Underwriting Decision";
  if (path.includes("/analyzing")) return "Analysis in Progress";
  if (path.includes("/upload")) return "Document Upload";
  if (path.includes("/report")) return "Case Analysis Report";
  if (path.startsWith("/cases/")) return "Case Detail";
  if (path.startsWith("/audit")) return "Audit Trail";
  if (path.startsWith("/admin")) return "Admin · User Management";
  if (path.startsWith("/settings")) return "Settings & Integrations";
  return "";
}

export function RiskPill({ level, score }: { level: "low" | "medium" | "high" | "critical"; score?: number }) {
  const map = {
    low: "bg-[var(--risk-low)]/15 text-[var(--risk-low)]",
    medium: "bg-[var(--risk-medium)]/20 text-[oklch(0.45_0.12_75)]",
    high: "bg-[var(--risk-high)]/15 text-[var(--risk-high)]",
    critical: "bg-[var(--risk-critical)]/15 text-[var(--risk-critical)]",
  } as const;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${map[level]}`}>
      <span
        className="size-1.5 rounded-full"
        style={{ backgroundColor: `var(--risk-${level})` }}
      />
      {score !== undefined ? `${score} · ` : ""}{level[0].toUpperCase() + level.slice(1)}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    Uploading: "bg-secondary text-secondary-foreground",
    Processing: "bg-[var(--info)]/15 text-[var(--info)]",
    "Ready for Review": "bg-primary-soft text-[var(--accent-foreground)]",
    "Decision Recorded": "bg-[var(--success)]/15 text-[var(--success)]",
  };
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${map[status] ?? "bg-secondary"}`}>
      {status}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl bg-surface text-surface-foreground border border-border shadow-[var(--shadow-card)] ${className}`}
    >
      {children}
    </div>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}