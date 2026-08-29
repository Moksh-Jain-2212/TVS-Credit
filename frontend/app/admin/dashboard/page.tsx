"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Metric, ProtectedRoute, StatusBadge, formatCurrency, formatPercent } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { getAdminDashboard, type AdminApplicationRow } from "@/lib/api";

export default function AdminDashboardPage() {
  const { accessToken } = useAuth();
  const [dashboard, setDashboard] = useState<{ counts: Record<string, number>; recent_applications: AdminApplicationRow[] } | null>(null);

  useEffect(() => {
    if (accessToken) {
      getAdminDashboard(accessToken).then(setDashboard).catch(() => setDashboard(null));
    }
  }, [accessToken]);

  const counts = dashboard?.counts ?? {};
  const rows = dashboard?.recent_applications ?? [];
  const chartData = (key: keyof AdminApplicationRow, fallback = "Pending") => {
    const grouped = new Map<string, number>();
    rows.forEach((row) => {
      const label = String(row[key] ?? fallback);
      grouped.set(label, (grouped.get(label) ?? 0) + 1);
    });
    return Array.from(grouped, ([name, value]) => ({ name: name.replaceAll("_", " "), value }));
  };
  return (
    <ProtectedRoute role="ADMIN">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="page-kicker">Loan Officer</p>
          <h1 className="page-title">Admin Dashboard</h1>
        </div>
        <Link className="btn-primary" href="/admin/applications">Review Applications</Link>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Pending" value={String(counts.pending_applications ?? 0)} />
        <Metric label="Under Analysis" value={String(counts.under_analysis ?? 0)} />
        <Metric label="Admin Review" value={String(counts.admin_review ?? 0)} />
        <Metric label="Approved" value={String(counts.approved ?? 0)} />
        <Metric label="Rejected" value={String(counts.rejected ?? 0)} />
        <Metric label="More Info" value={String(counts.more_information_required ?? 0)} />
      </div>
      <section className="mt-6 section-panel">
        <h2 className="text-xl font-bold">Portfolio Signals</h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {[
            ["NADI Decisions", chartData("nadi_recommendation")],
            ["Risk Bands", chartData("risk")],
            ["Confidence", chartData("confidence_band")],
          ].map(([title, data]) => (
            <div className="item-card" key={String(title)}>
              <div className="metric-label">{String(title)}</div>
              <div className="mt-3 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data as { name: string; value: number }[]}>
                    <CartesianGrid stroke="#eaecf0" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#175cd3" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="mt-6 section-panel">
        <h2 className="text-xl font-bold">Recent Applications</h2>
        <div className="mt-4 grid gap-3">
          {(dashboard?.recent_applications ?? []).map((application) => (
            <Link className="item-card block" href={`/admin/applications/${application.id}`} key={application.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-bold">{application.applicant}</div>
                  <div className="text-sm text-[color:var(--muted)]">
                    {formatCurrency(application.requested_amount)} · {application.nadi_recommendation ?? "NADI pending"} · risk {formatPercent(application.risk_probability)}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--muted)]">
                    Behavioral {formatPercent(application.behavioral_risk_probability)} · coverage {formatPercent(application.behavioral_data_coverage)}
                  </div>
                </div>
                <StatusBadge status={application.application_status} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </ProtectedRoute>
  );
}
