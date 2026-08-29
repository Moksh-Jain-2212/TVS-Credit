"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApplicationSummary, ProtectedRoute, formatCurrency, formatPercent } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { getPlatformApplication, type PlatformApplication } from "@/lib/api";

export default function UserApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [application, setApplication] = useState<PlatformApplication | null>(null);

  useEffect(() => {
    if (accessToken && id) {
      getPlatformApplication(Number(id), accessToken).then(setApplication).catch(() => setApplication(null));
    }
  }, [accessToken, id]);

  return (
    <ProtectedRoute role="USER">
      {application ? (
        <div className="grid gap-6">
          <ApplicationSummary application={application} />
          <section className="section-panel">
            <h2 className="text-xl font-bold">Decision</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="metric-card"><div className="metric-label">Requested</div><div className="metric-value">{formatCurrency(application.requested_amount)}</div></div>
              <div className="metric-card"><div className="metric-label">Recommended</div><div className="metric-value">{formatCurrency(application.latest_underwriting?.recommended_amount)}</div></div>
              <div className="metric-card"><div className="metric-label">Approved</div><div className="metric-value">{formatCurrency(application.latest_admin_decision?.approved_amount)}</div></div>
            </div>
            {application.latest_underwriting?.borrower_explanation ? (
              <div className="mt-4 text-sm leading-6 text-[color:var(--muted)]">
                {Object.values(application.latest_underwriting.borrower_explanation).flat().filter(Boolean).slice(0, 4).join(" ")}
              </div>
            ) : null}
          </section>
          {application.latest_underwriting?.behavioral_risk ? (
            <section className="section-panel">
              <h2 className="text-xl font-bold">Behavioral Evidence</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="metric-card"><div className="metric-label">Coverage</div><div className="metric-value">{formatPercent(application.latest_underwriting.behavioral_risk.behavioral_data_coverage)}</div></div>
                <div className="metric-card"><div className="metric-label">Evidence Confidence</div><div className="metric-value">{Math.round(application.latest_underwriting.behavioral_risk.behavioral_assessment_confidence ?? 0)} / 100</div></div>
                <div className="metric-card"><div className="metric-label">Current Risk</div><div className="metric-value">{formatPercent(application.latest_underwriting.behavioral_risk.combined_risk_probability)}</div></div>
              </div>
            </section>
          ) : null}
          <section className="section-panel">
            <h2 className="text-xl font-bold">Status Feedback</h2>
            <div className="mt-4 grid gap-2">
              {(application.notifications ?? []).map((message) => <div key={message} className="border-b border-[color:var(--line)] py-2 text-sm last:border-b-0">{message}</div>)}
            </div>
          </section>
        </div>
      ) : <div className="empty-state">Loading application</div>}
    </ProtectedRoute>
  );
}
