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
  formatPercent,
} from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import {
  analyzeAdminApplication,
  decideAdminApplication,
  generateGrokExplanation,
  getAdminApplication,
  type AdminApplicationDetail,
  type GrokExplanation,
} from "@/lib/api";

const decisions = [
  "APPROVE_REQUESTED",
  "APPROVE_RECOMMENDED",
  "REQUEST_MORE_INFORMATION",
  "REJECT",
];

function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="section-panel">
      <summary className="cursor-pointer text-xl font-bold">{title}</summary>
      <pre className="mt-4 max-h-72 overflow-auto bg-[#f8fafc] p-3 text-xs">{JSON.stringify(value ?? {}, null, 2)}</pre>
    </details>
  );
}

function ValueLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-[color:var(--line)] py-2 text-sm">
      <span className="text-[color:var(--muted)]">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  );
}

function BehavioralRiskBreakdown({ detail }: { detail: AdminApplicationDetail }) {
  const factors = detail.behavioral_risk.factor_contributions.slice(0, 6);
  return (
    <section className="section-panel">
      <h2 className="text-xl font-bold">Behavioral Risk</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Metric label="Behavioral Score" value={detail.behavioral_risk.score !== null ? `${Math.round(detail.behavioral_risk.score)} / 100` : "Not available"} />
        <Metric label="Coverage" value={formatPercent(detail.behavioral_risk.coverage)} />
        <Metric label="Assessment Confidence" value={detail.behavioral_risk.assessment_confidence !== null ? `${Math.round(detail.behavioral_risk.assessment_confidence)} / 100` : "Not available"} />
      </div>
      <div className="mt-4 grid gap-2">
        {factors.length ? factors.map((factor, index) => (
          <div className="item-card" key={`${factor.source}-${factor.name}-${index}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-bold">{String(factor.source)} · {String(factor.name).replaceAll("_", " ")}</span>
              <span className={`badge ${factor.direction === "supportive" ? "badge-good" : factor.direction === "adverse" ? "badge-bad" : "badge-neutral"}`}>{String(factor.direction)}</span>
            </div>
            <div className="mt-2 text-sm text-[color:var(--muted)]">Risk score {String(factor.risk_score)} · contribution {String(factor.contribution_pct)}%</div>
          </div>
        )) : <div className="empty-state">No connected behavioral source factors yet</div>}
      </div>
    </section>
  );
}

function DataSourceCoverage({ detail }: { detail: AdminApplicationDetail }) {
  return (
    <section className="section-panel">
      <h2 className="text-xl font-bold">Data Source Coverage</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {detail.alternative_data.sources.map((source) => (
          <div className="item-card" key={source.source_type}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold">{source.label}</span>
              <span className={source.active ? "badge badge-good" : "badge badge-neutral"}>{source.active ? "Active" : "Missing"}</span>
            </div>
            <ValueLine label="Mode" value={source.connection_mode ?? "NA"} />
            <ValueLine label="Quality" value={source.quality_score !== null ? `${Math.round(source.quality_score * 100)}%` : "NA"} />
          </div>
        ))}
      </div>
    </section>
  );
}

function GrokPanel({ explanation, loading, onGenerate }: { explanation: GrokExplanation | null; loading: boolean; onGenerate: () => void }) {
  const response = explanation?.structured_response;
  return (
    <section className="section-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Grok Explanation</h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{explanation ? `${explanation.provider} · ${explanation.model} · ${explanation.status}` : "No explanation generated yet"}</p>
        </div>
        <button className="btn-secondary" disabled={loading} type="button" onClick={onGenerate}>{loading ? "Generating" : "Generate"}</button>
      </div>
      {response ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div>
            <div className="metric-label">Executive Summary</div>
            <p className="mt-1 text-sm">{response.executive_summary}</p>
          </div>
          <div>
            <div className="metric-label">Borrower Summary</div>
            <p className="mt-1 text-sm">{response.borrower_friendly_summary}</p>
          </div>
          <div>
            <div className="metric-label">Risk Drivers</div>
            <ul className="mt-1 list-disc pl-5 text-sm">{response.risk_drivers.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
          <div>
            <div className="metric-label">Evidence Gaps</div>
            <ul className="mt-1 list-disc pl-5 text-sm">{response.evidence_gaps.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        </div>
      ) : <div className="mt-4 empty-state">Generate a structured loan-officer explanation</div>}
    </section>
  );
}

export default function AdminApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [detail, setDetail] = useState<AdminApplicationDetail | null>(null);
  const [grokExplanation, setGrokExplanation] = useState<GrokExplanation | null>(null);
  const [decision, setDecision] = useState("APPROVE_RECOMMENDED");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (accessToken && id) {
      const loaded = await getAdminApplication(Number(id), accessToken);
      setDetail(loaded);
      setGrokExplanation(loaded.explanations.grok);
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

  async function generateGrok() {
    if (!accessToken || !id) return;
    setLoading(true);
    setError(null);
    try {
      setGrokExplanation(await generateGrokExplanation(Number(id), accessToken));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Grok explanation failed");
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
            <Metric label="Current Risk" value={formatPercent(detail.risk.combined_probability ?? detail.risk.probability)} />
            <Metric label="NADI Recommendation" value={detail.nadi_recommendation.decision ?? "Pending"} />
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
              <h2 className="text-xl font-bold">Risk Profile</h2>
              <div className="mt-4"><RiskBadge value={detail.risk.probability} band={detail.risk.band} /></div>
              <div className="mt-4">
                <ValueLine label="Historical model risk" value={formatPercent(detail.risk.historical_model_probability)} />
                <ValueLine label="Behavioral risk" value={formatPercent(detail.risk.behavioral_probability)} />
                <ValueLine label="Final current risk" value={formatPercent(detail.risk.combined_probability ?? detail.risk.probability)} />
              </div>
            </div>
            <div className="section-panel">
              <ConfidenceGauge score={detail.evidence_confidence.score} band={detail.evidence_confidence.band} />
            </div>
          </section>

          <BehavioralRiskBreakdown detail={detail} />
          <DataSourceCoverage detail={detail} />
          <GrokPanel explanation={grokExplanation} loading={loading} onGenerate={generateGrok} />

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

          <JsonPanel title="Developer Details: Financial Pulse" value={detail.financial_profile} />
          <JsonPanel title="Developer Details: Cash-flow Forecast" value={detail.forecast} />
          <JsonPanel title="Developer Details: Stress Tests" value={detail.stress_test} />
          <JsonPanel title="Developer Details: Explainability" value={detail.explanations.loan_officer} />
          <JsonPanel title="Developer Details: Audit History" value={detail.audit_history} />
        </div>
      ) : <div className="empty-state">Loading application</div>}
    </ProtectedRoute>
  );
}
