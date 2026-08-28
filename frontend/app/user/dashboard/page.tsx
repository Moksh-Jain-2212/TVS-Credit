"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { ApplicationSummary, Metric, ProtectedRoute } from "@/components/platform";
import { listPlatformApplications, type PlatformApplication } from "@/lib/api";

export default function UserDashboardPage() {
  const { user, accessToken } = useAuth();
  const [applications, setApplications] = useState<PlatformApplication[]>([]);

  useEffect(() => {
    if (accessToken) {
      listPlatformApplications(accessToken).then(setApplications).catch(() => setApplications([]));
    }
  }, [accessToken]);

  const latest = applications[0];
  const counts = useMemo(() => ({
    total: applications.length,
    active: applications.filter((item) => !["APPROVED", "REJECTED", "CANCELLED"].includes(item.status)).length,
    final: applications.filter((item) => ["APPROVED", "REJECTED"].includes(item.status)).length,
  }), [applications]);

  return (
    <ProtectedRoute role="USER">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-[color:var(--accent)]">Borrower Dashboard</p>
          <h1 className="text-3xl font-black">Welcome, {user?.name}</h1>
        </div>
        <Link className="btn-primary" href="/user/apply">Apply for Loan</Link>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Applications" value={String(counts.total)} />
        <Metric label="In Progress" value={String(counts.active)} />
        <Metric label="Final Decisions" value={String(counts.final)} />
      </div>
      <section className="mt-6">
        {latest ? <ApplicationSummary application={latest} /> : <div className="empty-state">No applications yet</div>}
      </section>
      <section className="mt-6 section-panel">
        <h2 className="text-xl font-bold">Status Feedback</h2>
        <div className="mt-4 grid gap-2">
          {(latest?.notifications ?? ["Application submitted", "Application under analysis", "Application awaiting admin review", "More information requested", "Approved", "Rejected"]).map((message) => (
            <div key={message} className="border-b border-[color:var(--line)] py-2 text-sm last:border-b-0">{message}</div>
          ))}
        </div>
      </section>
    </ProtectedRoute>
  );
}
