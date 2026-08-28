"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import {
  ConfidenceGauge,
  Metric,
  ProtectedRoute,
  RepaymentEnvelope,
  RiskBadge,
  StatusBadge,
  TransactionTable,
  formatCurrency,
} from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import {
  analyzeAdminApplication,
  decideAdminApplication,
  getAdminApplication,
  type AdminApplicationDetail,
} from "@/lib/api";

const decisions = [
  "APPROVE_REQUESTED",
  "APPROVE_RECOMMENDED",
  "REQUEST_MORE_INFORMATION",
  "REJECT",
];

function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="section-panel">
      <h2 className="text-xl font-bold">{title}</h2>
      <pre className="mt-4 max-h-72 overflow-auto bg-[#f8fafc] p-3 text-xs">{JSON.stringify(value ?? {}, null, 2)}</pre>
    </section>
  );
}

export default function AdminApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [detail, setDetail] = useState<AdminApplicationDetail | null>(null);
  const [decision, setDecision] = useState("APPROVE_RECOMMENDED");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (accessToken && id) {
      setDetail(await getAdminApplication(Number(id), accessToken));
    }
  }

  useEffect(() => {
    load().catch(() => setDetail(null));
  }, [accessToken, id]);

  async function analyze() {
    if (!accessToken || !id) return;
    setLoading(true);
    setError(null);
    try {
      setDetail(await analyzeAdminApplication(Number(id), accessToken));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitDecision(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !id) return;
    setLoading(true);
    setError(null);
    try {
      setDetail(await decideAdminApplication(Number(id), { decision, remarks }, accessToken));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Decision failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ProtectedRoute role="ADMIN">
      {detail ? (
        <div className="grid gap-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-[color:var(--accent)]">Application #{detail.application.id}</p>
              <h1 className="text-3xl font-black">{detail.borrower.name}</h1>
            </div>
            <StatusBadge status={detail.application.status} />
          </div>

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Requested Amount" value={formatCurrency(detail.application.requested_amount)} />
            <Metric label="Maximum Safe Exposure" value={formatCurrency(detail.nadi_recommendation.maximum_safe_exposure)} />
            <Metric label="Recommended Amount" value={formatCurrency(detail.nadi_recommendation.recommended_amount)} />
            <Metric label="Approved Amount" value={formatCurrency(detail.application.latest_admin_decision?.approved_amount)} />
          </section>

          <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
            <div className="section-panel">
              <h2 className="text-xl font-bold">Borrower</h2>
              <div className="mt-4 grid gap-3 text-sm">
                <div>{detail.borrower.email}</div>
                <div>{detail.borrower.phone ?? "No phone"}</div>
                <div>{detail.application.employment_type ?? "Employment not supplied"}</div>
              </div>
            </div>
            <div className="section-panel">
              <h2 className="text-xl font-bold">Loan Request</h2>
              <div className="mt-4 grid gap-3 text-sm">
                <div>{formatCurrency(detail.application.requested_amount)} / {detail.application.requested_tenure ?? "NA"} months</div>
                <div>{detail.application.loan_purpose ?? "No purpose"}</div>
                <div>{detail.linked_financial_evidence.label ?? "Financial evidence pending"}</div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 sm:grid-cols-3">
            <Metric label="Declared Income" value={formatCurrency(detail.application.declared_monthly_income)} />
            <Metric label="Declared Expenses" value={formatCurrency(detail.application.declared_monthly_expenses)} />
            <Metric label="Existing EMI" value={formatCurrency(detail.application.existing_monthly_emi)} />
          </section>

          <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
            <div className="section-panel">
              <h2 className="text-xl font-bold">Risk</h2>
              <div className="mt-4"><RiskBadge value={detail.risk.probability} band={detail.risk.band} /></div>
            </div>
            <div className="section-panel">
              <ConfidenceGauge score={detail.evidence_confidence.score} band={detail.evidence_confidence.band} />
            </div>
          </section>

          <section className="section-panel">
            <h2 className="text-xl font-bold">Repayment Envelope</h2>
            <div className="mt-4">
              <RepaymentEnvelope candidates={detail.repayment_envelope?.all_evaluated_combinations ?? []} />
            </div>
          </section>

          <section className="section-panel">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold">NADI Recommendation vs Final Admin Decision</h2>
                <p className="mt-1 text-sm text-[color:var(--muted)]">{detail.nadi_recommendation.reasons?.[0] ?? "NADI recommendation pending"}</p>
              </div>
              <button className="btn-secondary" disabled={loading} type="button" onClick={analyze}>Run Analysis</button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="metric-card"><div className="metric-label">NADI Recommendation</div><div className="metric-value">{detail.nadi_recommendation.decision ?? "Pending"}</div></div>
              <div className="metric-card"><div className="metric-label">Final Admin Decision</div><div className="metric-value">{detail.application.latest_admin_decision?.decision ?? "Pending"}</div></div>
            </div>
          </section>

          <section className="section-panel">
            <h2 className="text-xl font-bold">Transactions</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Metric label="Avg Inflow" value={formatCurrency(Number(detail.transaction_summary.average_monthly_inflow ?? 0))} />
              <Metric label="Avg Outflow" value={formatCurrency(Number(detail.transaction_summary.average_monthly_outflow ?? 0))} />
              <Metric label="Net Cash Flow" value={formatCurrency(Number(detail.transaction_summary.net_monthly_cash_flow ?? 0))} />
            </div>
            <div className="mt-4"><TransactionTable transactions={detail.transactions} /></div>
          </section>

          <form className="section-panel" onSubmit={submitDecision}>
            <h2 className="text-xl font-bold">Admin Decision</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-[260px_1fr]">
              <label>
                <span className="label">Decision</span>
                <select className="field" value={decision} onChange={(event) => setDecision(event.target.value)}>
                  {decisions.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
                </select>
              </label>
              <label>
                <span className="label">Remarks</span>
                <input className="field" value={remarks} onChange={(event) => setRemarks(event.target.value)} />
              </label>
            </div>
            {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
            <button className="btn-primary mt-5" disabled={loading} type="submit">{loading ? "Saving" : "Save Decision"}</button>
          </form>

          <JsonPanel title="Financial Pulse" value={detail.financial_profile} />
          <JsonPanel title="Cash-flow Forecast" value={detail.forecast} />
          <JsonPanel title="Stress Tests" value={detail.stress_test} />
          <JsonPanel title="Explainability" value={detail.explanations.loan_officer} />
          <JsonPanel title="Audit History" value={detail.audit_history} />
        </div>
      ) : <div className="empty-state">Loading application</div>}
    </ProtectedRoute>
  );
}
