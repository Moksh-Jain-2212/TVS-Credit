"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = status ?? "UNKNOWN";
  const tone = value === "APPROVED" ? "good" : value === "REJECTED" ? "bad" : value === "MORE_INFORMATION_REQUIRED" ? "warn" : "neutral";
  return <span className={`badge badge-${tone}`}>{value.replaceAll("_", " ")}</span>;
}

export function RiskBadge({ value, band }: { value?: number | null; band?: string | null }) {
  const tone = band === "low" ? "good" : band === "high" ? "bad" : "warn";
  return <span className={`badge badge-${tone}`}>{band ?? "risk unavailable"} {value !== undefined ? formatPercent(value) : ""}</span>;
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
  const base = user?.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard";
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[color:var(--line)] bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <Link href={base} className="text-lg font-black tracking-[0]">TVS NADI</Link>
          <nav className="flex flex-wrap items-center gap-2 text-sm">
            {user?.role === "USER" ? (
              <>
                <Link className="nav-link" href="/user/dashboard">Dashboard</Link>
                <Link className="nav-link" href="/user/applications">Applications</Link>
                <Link className="nav-link" href="/user/apply">Apply</Link>
              </>
            ) : null}
            {user?.role === "ADMIN" ? (
              <>
                <Link className="nav-link" href="/admin/dashboard">Dashboard</Link>
                <Link className="nav-link" href="/admin/applications">Applications</Link>
                <Link className="nav-link" href="/demo">Demo</Link>
              </>
            ) : null}
            <button
              className="btn-secondary"
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
      <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
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
        <Metric label="Financial Data" value={application.demo_financial_profile_connected ? "Demo bank data connected" : "Not connected"} />
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
