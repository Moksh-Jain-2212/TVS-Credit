"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProtectedRoute, RiskBadge, StatusBadge, formatCurrency, formatPercent } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { listAdminApplications, type AdminApplicationRow } from "@/lib/api";

export default function AdminApplicationsPage() {
  const { accessToken } = useAuth();
  const [applications, setApplications] = useState<AdminApplicationRow[]>([]);

  useEffect(() => {
    if (accessToken) {
      listAdminApplications(accessToken).then(setApplications).catch(() => setApplications([]));
    }
  }, [accessToken]);

  return (
    <ProtectedRoute role="ADMIN">
      <h1 className="text-3xl font-black">Applications</h1>
      <section className="mt-6 section-panel overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Applicant</th>
              <th>Requested Amount</th>
              <th>Submitted Date</th>
              <th>Risk</th>
              <th>Behavioral</th>
              <th>Coverage</th>
              <th>Confidence</th>
              <th>NADI Recommendation</th>
              <th>Application Status</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((application) => (
              <tr key={application.id}>
                <td><Link className="font-bold text-[color:var(--accent)]" href={`/admin/applications/${application.id}`}>{application.applicant}</Link></td>
                <td>{formatCurrency(application.requested_amount)}</td>
                <td>{application.submitted_at ? new Date(application.submitted_at).toLocaleDateString("en-IN") : "Not submitted"}</td>
                <td><RiskBadge value={application.risk_probability} band={application.risk} /></td>
                <td>{formatPercent(application.behavioral_risk_probability)}</td>
                <td>{formatPercent(application.behavioral_data_coverage)}</td>
                <td>{application.confidence_score ?? "NA"} · {application.confidence_band ?? "NA"}</td>
                <td>{application.nadi_recommendation ?? "Pending"}</td>
                <td><StatusBadge status={application.application_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </ProtectedRoute>
  );
}
