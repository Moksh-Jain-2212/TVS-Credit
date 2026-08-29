"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import type { PlatformApplication, PlatformTransaction, RepaymentCandidate } from "@/lib/api";

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  return `${Math.round(value * 100)}%`;
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="skeleton grid place-items-center text-sm font-bold text-[color:var(--muted)]">{label}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty-state flex flex-wrap items-center justify-between gap-3 border-red-200 bg-red-50 text-red-800">
      <span>{message}</span>
      {onRetry ? <button className="btn-secondary" type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = status ?? "UNKNOWN";
  const tone = value === "APPROVED" ? "good" : value === "REJECTED" ? "bad" : value === "MORE_INFORMATION_REQUIRED" ? "warn" : "neutral";
  return <span className={`badge badge-${tone}`}>{value.replaceAll("_", " ")}</span>;
}

export function RiskBadge({ value, band }: { value?: number | null; band?: string | null }) {
  const tone = band === "low" ? "good" : band === "high" ? "bad" : "warn";
  const label = band ? `${band[0].toUpperCase()}${band.slice(1)}` : "Risk unavailable";
  return <span className={`badge badge-${tone}`}>{label} {value !== undefined ? formatPercent(value) : ""}</span>;
}

export function ConfidenceGauge({ score, band }: { score: number | null | undefined; band?: string | null }) {
  const width = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold">Evidence Confidence</span>
        <span className="text-[color:var(--muted)]">{score ?? "NA"} / 100 {band ? `(${band})` : ""}</span>
      </div>
      <div className="mt-2 h-2 bg-[#e5e7eb]">
        <div className="h-2 bg-[color:var(--accent)]" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value mt-1">{value}</div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const base = user?.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard";
  const links = user?.role === "ADMIN"
    ? [
        ["Dashboard", "/admin/dashboard"],
        ["Applications", "/admin/applications"],
        ["Review Queue", "/admin/applications?status=ADMIN_REVIEW"],
        ["System / Model Info", "/demo"],
      ]
    : [
        ["Dashboard", "/user/dashboard"],
        ["Applications", "/user/applications"],
        ["Apply", "/user/apply"],
      ];
  if (user?.role === "ADMIN") {
    return (
      <div className="app-frame app-frame-admin">
        <aside className="sidebar hidden min-h-screen p-5 lg:block">
          <Link href={base} className="text-xl font-black">TVS NADI</Link>
          <div className="mt-2 text-xs font-bold uppercase text-slate-400">Underwriting OS</div>
          <nav className="mt-8 grid gap-2 text-sm">
            {links.map(([label, href]) => {
              const hrefPath = href.split("?")[0];
              const active = pathname === hrefPath || (hrefPath !== base && pathname.startsWith(hrefPath));
              return <Link className={`nav-link justify-start ${active ? "nav-link-active" : ""}`} href={href} key={href}>{label}</Link>;
            })}
          </nav>
        </aside>
        <div>
          <header className="topbar sticky top-0 z-20">
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <div>
                <div className="text-xs font-bold uppercase text-[color:var(--muted)]">Production Prototype</div>
                <div className="font-black leading-tight">{user.name}</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="badge badge-info">Local</span>
                <button className="btn-secondary" type="button" onClick={() => { logout(); router.push("/login"); }}>Logout</button>
              </div>
              <nav className="flex w-full gap-2 overflow-x-auto pb-1 text-sm lg:hidden">
                {links.map(([label, href]) => {
                  const hrefPath = href.split("?")[0];
                  const active = pathname === hrefPath || (hrefPath !== base && pathname.startsWith(hrefPath));
                  return <Link className={`btn-secondary min-w-max ${active ? "border-[color:var(--accent)] text-[color:var(--accent)]" : ""}`} href={href} key={href}>{label}</Link>;
                })}
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-4 py-5 sm:px-5 lg:py-6">{children}</main>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 bg-[color:var(--ink)] text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <Link href={base} className="text-lg font-black">TVS NADI</Link>
          <nav className="flex flex-wrap items-center gap-2 text-sm">
            {links.map(([label, href]) => {
              const active = pathname === href || pathname.startsWith(href);
              return <Link className={`nav-link ${active ? "nav-link-active" : ""}`} href={href} key={href}>{label}</Link>;
            })}
            <button
              className="btn-secondary border-white/20 bg-white/10 text-white hover:bg-white/15"
              type="button"
              onClick={() => {
                logout();
                router.push("/login");
              }}
            >
              Logout
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-5 lg:py-6">{children}</main>
    </div>
  );
}

export function ApplicationSummary({ application }: { application: PlatformApplication }) {
  return (
    <div className="item-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-[color:var(--muted)]">Application #{application.id}</div>
          <h2 className="mt-1 text-xl font-bold">{formatCurrency(application.requested_amount)}</h2>
        </div>
        <StatusBadge status={application.status} />
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Metric label="Tenure" value={application.requested_tenure ? `${application.requested_tenure} months` : "Not set"} />
        <Metric label="Purpose" value={application.loan_purpose ?? "Not set"} />
        <Metric label="Borrower Type" value={application.latest_underwriting?.segment_analysis?.borrower_segment_label ?? application.borrower_segment?.replaceAll("_", " ") ?? "Not set"} />
      </div>
    </div>
  );
}

export function RepaymentEnvelope({ candidates }: { candidates: RepaymentCandidate[] }) {
  if (!candidates?.length) {
    return <div className="empty-state">Repayment envelope unavailable</div>;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {candidates.map((candidate) => (
        <div key={`${candidate.amount}-${candidate.tenure_months}`} className={`envelope-cell envelope-${candidate.classification.toLowerCase()}`}>
          <div className="text-sm font-bold">{formatCurrency(candidate.amount)}</div>
          <div className="text-xs">{candidate.tenure_months} mo · {formatCurrency(candidate.estimated_emi)}</div>
          <div className="mt-1 text-[0.68rem] font-bold">{candidate.classification}</div>
        </div>
      ))}
    </div>
  );
}

export function TransactionTable({ transactions }: { transactions: PlatformTransaction[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Operation</th>
            <th>Amount</th>
            <th>Balance</th>
            <th>Category</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((transaction, index) => (
            <tr key={`${transaction.date}-${transaction.amount}-${index}`}>
              <td>{transaction.date}</td>
              <td>{transaction.type}</td>
              <td>{transaction.operation ?? "NA"}</td>
              <td>{formatCurrency(transaction.amount)}</td>
              <td>{formatCurrency(transaction.balance)}</td>
              <td>{transaction.category ?? "NA"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProtectedRoute({ role, children }: { role: "USER" | "ADMIN"; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) {
      return;
    }
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== role) {
      router.replace(user.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard");
    }
  }, [loading, role, router, user]);

  if (loading) {
    return <div className="page-center">Loading session</div>;
  }
  if (!user) {
    return <div className="page-center">Redirecting</div>;
  }
  if (user.role !== role) {
    return <div className="page-center">Redirecting</div>;
  }
  return <AppShell>{children}</AppShell>;
}
