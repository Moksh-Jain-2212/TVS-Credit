"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { ApplicationSummary, ErrorState, LoadingState, Metric, ProtectedRoute } from "@/components/platform";
import { listPlatformApplications, type PlatformApplication } from "@/lib/api";

const journey = ["Application", "Evidence", "NADI Analysis", "Loan Officer Review", "Decision"];

function stageIndex(status: string | undefined) {
  if (!status || status === "DRAFT") return 0;
  if (status === "SUBMITTED" || status === "UNDER_ANALYSIS") return 2;
  if (status === "ADMIN_REVIEW" || status === "MORE_INFORMATION_REQUIRED") return 3;
  return 4;
}

export default function UserDashboardPage() {
  const { user, accessToken } = useAuth();
  const [applications, setApplications] = useState<PlatformApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      setApplications(await listPlatformApplications(accessToken));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load applications");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [accessToken]);

  const latest = applications[0];
  const currentStage = stageIndex(latest?.status);
  const counts = useMemo(() => ({
    total: applications.length,
    active: applications.filter((item) => !["APPROVED", "REJECTED", "CANCELLED"].includes(item.status)).length,
    final: applications.filter((item) => ["APPROVED", "REJECTED"].includes(item.status)).length,
  }), [applications]);

  return (
    <ProtectedRoute role="USER">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="page-kicker">Hello, {user?.name}</p>
          <h1 className="page-title">Your Credit Journey</h1>
        </div>
        <Link className="btn-primary" href="/user/apply">Apply for Loan</Link>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Metric label="Applications" value={String(counts.total)} />
        <Metric label="In Progress" value={String(counts.active)} />
        <Metric label="Final Decisions" value={String(counts.final)} />
      </div>
      <section className="mt-6 section-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-bold">Application Progress</h2>
          {latest ? <Link className="btn-secondary" href={`/user/applications/${latest.id}`}>Open latest</Link> : null}
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-5">
          {journey.map((item, index) => (
            <div className={`step-item ${index === currentStage ? "step-item-active" : index < currentStage ? "step-item-complete" : ""}`} key={item}>
              <div className="step-dot">{index + 1}</div>
              <div className="text-sm font-bold">{item}</div>
            </div>
          ))}
        </div>
      </section>
      <section className="mt-6">
        {loading ? <LoadingState label="Loading applications" /> : error ? <ErrorState message={error} onRetry={load} /> : latest ? <ApplicationSummary application={latest} /> : <div className="empty-state">No applications yet</div>}
      </section>
      <section className="mt-6 section-panel">
        <h2 className="text-xl font-bold">Recent Updates</h2>
        <div className="mt-4 grid gap-2">
          {(latest?.notifications ?? ["Create an application to begin your NADI journey."]).map((message) => (
            <div key={message} className="border-b border-[color:var(--line)] py-2 text-sm last:border-b-0">{message}</div>
          ))}
        </div>
      </section>
    </ProtectedRoute>
  );
}
