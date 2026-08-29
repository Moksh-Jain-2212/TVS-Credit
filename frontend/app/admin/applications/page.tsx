"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorState, LoadingState, ProtectedRoute, RiskBadge, StatusBadge, formatCurrency, formatPercent } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { listAdminApplications, type AdminApplicationRow } from "@/lib/api";

const pageSize = 10;

export default function AdminApplicationsPage() {
  const { accessToken } = useAuth();
  const [applications, setApplications] = useState<AdminApplicationRow[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [confidence, setConfidence] = useState("");
  const [sortKey, setSortKey] = useState<"submitted" | "risk" | "amount">("submitted");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      setApplications(await listAdminApplications(accessToken, { status, risk_band: risk, confidence_band: confidence, limit: 250 }));
      setPage(0);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load applications");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [accessToken, status, risk, confidence]);

  const visible = useMemo(() => {
    const filtered = applications.filter((application) => {
      const haystack = `${application.applicant} ${application.applicant_email} ${application.nadi_recommendation ?? ""}`.toLowerCase();
      return haystack.includes(search.toLowerCase());
    });
    filtered.sort((a, b) => {
      if (sortKey === "risk") return (b.risk_probability ?? -1) - (a.risk_probability ?? -1);
      if (sortKey === "amount") return (b.requested_amount ?? 0) - (a.requested_amount ?? 0);
      return new Date(b.submitted_at ?? 0).getTime() - new Date(a.submitted_at ?? 0).getTime();
    });
    return filtered;
  }, [applications, search, sortKey]);
  const pageRows = visible.slice(page * pageSize, page * pageSize + pageSize);
  const maxPage = Math.max(0, Math.ceil(visible.length / pageSize) - 1);

  return (
    <ProtectedRoute role="ADMIN">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="page-kicker">Review Queue</p>
          <h1 className="page-title">Applications</h1>
        </div>
        <span className="badge badge-info">{visible.length} visible</span>
      </div>
      <section className="mt-6 section-panel">
        <div className="grid gap-3 md:grid-cols-5">
          <input className="field md:col-span-2" placeholder="Search applicant or recommendation" value={search} onChange={(event) => setSearch(event.target.value)} />
          <select className="field" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            {["SUBMITTED", "UNDER_ANALYSIS", "ADMIN_REVIEW", "MORE_INFORMATION_REQUIRED", "APPROVED", "REJECTED"].map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
          </select>
          <select className="field" value={risk} onChange={(event) => setRisk(event.target.value)}>
            <option value="">All risk</option>
            {["low", "medium", "high"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select className="field" value={confidence} onChange={(event) => setConfidence(event.target.value)}>
            <option value="">All confidence</option>
            {["low", "medium", "high"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {(["submitted", "risk", "amount"] as const).map((item) => (
            <button className={sortKey === item ? "btn-primary min-w-max" : "btn-secondary min-w-max"} type="button" onClick={() => setSortKey(item)} key={item}>Sort by {item}</button>
          ))}
        </div>
      </section>
      <section className="mt-6 section-panel overflow-x-auto">
        {loading ? <LoadingState label="Loading review queue" /> : error ? <ErrorState message={error} onRetry={load} /> : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Requested</th>
                  <th>Submitted</th>
                  <th>Current status</th>
                  <th>Risk</th>
                  <th>Evidence</th>
                  <th>Coverage</th>
                  <th>NADI</th>
                  <th>Recommended</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((application) => (
                  <tr key={application.id}>
                    <td><Link className="font-bold text-[color:var(--accent)]" href={`/admin/applications/${application.id}`}>{application.applicant}</Link><div className="text-xs text-[color:var(--muted)]">{application.applicant_email}</div></td>
                    <td>{formatCurrency(application.requested_amount)}</td>
                    <td>{application.submitted_at ? new Date(application.submitted_at).toLocaleDateString("en-IN") : "Not submitted"}</td>
                    <td><StatusBadge status={application.application_status} /></td>
                    <td><RiskBadge value={application.risk_probability} band={application.risk} /></td>
                    <td>{application.confidence_score ?? "NA"} · {application.confidence_band ?? "NA"}</td>
                    <td>{formatPercent(application.behavioral_data_coverage)}</td>
                    <td>{application.nadi_recommendation ?? "Pending"}</td>
                    <td>{formatCurrency(application.recommended_amount)}</td>
                    <td><Link className="btn-secondary" href={`/admin/applications/${application.id}`}>Review</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!pageRows.length ? <div className="mt-4 empty-state">No applications match these filters</div> : null}
            <div className="mt-4 flex items-center justify-between gap-3">
              <button className="btn-secondary" disabled={page === 0} type="button" onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous</button>
              <span className="text-sm text-[color:var(--muted)]">Page {page + 1} of {maxPage + 1}</span>
              <button className="btn-secondary" disabled={page >= maxPage} type="button" onClick={() => setPage((value) => Math.min(maxPage, value + 1))}>Next</button>
            </div>
          </>
        )}
      </section>
    </ProtectedRoute>
  );
}
