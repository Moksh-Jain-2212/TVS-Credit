"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ConfidenceGauge,
  Metric,
  ProtectedRoute,
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
  type RepaymentCandidate,
  type SegmentAnalysis,
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

function formatMetricValue(key: string, value: number | string | null | undefined): string {
  if (typeof value === "number") {
    if (/(ratio|volatility|stability|trend|regularity|consistency|strength)/.test(key)) {
      return formatPercent(value);
    }
    if (/(amount|income|salary|turnover|expense|surplus|balance|emi|cash_flow|outflow|inflow|settlement)/.test(key)) {
      return formatCurrency(value);
    }
    return String(Math.round(value * 100) / 100);
  }
  return value === null || value === undefined || value === "" ? "Not available" : String(value).replaceAll("_", " ");
}

function SegmentFinancialPanel({ analysis }: { analysis: SegmentAnalysis }) {
  const segmentMetrics = Object.entries(analysis.segment_specific_features);
  const commonMetrics = Object.entries(analysis.common_financial_features).slice(0, 8);
  return (
    <section className="section-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="page-kicker">{analysis.borrower_segment_label}</p>
          <h2 className="text-xl font-bold">Segment-Aware Capacity</h2>
        </div>
        <span className="badge badge-info">{analysis.borrower_segment.replaceAll("_", " ")}</span>
      </div>
      <p className="mt-3 text-sm text-[color:var(--muted)]">{analysis.income_interpretation}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Conservative Income" value={formatCurrency(analysis.conservative_income)} />
        <Metric label="Sustainable Surplus" value={formatCurrency(analysis.sustainable_monthly_surplus)} />
        <Metric label="Relevant Evidence" value={analysis.relevant_evidence.join(", ")} />
        <Metric label="Connected Relevant" value={analysis.connected_relevant_evidence.length ? analysis.connected_relevant_evidence.join(", ") : "None"} />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="font-bold">Common Financial Metrics</h3>
          <div className="mt-3 grid gap-2">
            {commonMetrics.map(([key, value]) => <ValueLine key={key} label={key.replaceAll("_", " ")} value={formatMetricValue(key, value)} />)}
          </div>
        </div>
        <div>
          <h3 className="font-bold">Relevant Segment Metrics</h3>
          <div className="mt-3 grid gap-2">
            {segmentMetrics.map(([key, value]) => <ValueLine key={key} label={key.replaceAll("_", " ")} value={formatMetricValue(key, value)} />)}
          </div>
        </div>
      </div>
    </section>
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
      <p className="mt-3 text-xs font-bold text-[color:var(--muted)]">Calibration: {detail.behavioral_risk.calibration_status ?? "Not available"}</p>
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
              <div className="flex gap-2">
                {source.snapshot?.provenance?.evidence_origin === "PARAMETERIZED_SYNTHETIC_DEMO" ? <span className="badge badge-info">Synthetic demo</span> : null}
                <span className={source.active ? "badge badge-good" : source.segment_relevant ? "badge badge-info" : "badge badge-neutral"}>
                  {source.active ? "Active" : source.segment_relevant ? "Relevant" : "Optional"}
                </span>
              </div>
            </div>
            <ValueLine label="Mode" value={source.connection_mode ?? "NA"} />
            <ValueLine label="Quality" value={source.quality_score !== null ? `${Math.round(source.quality_score * 100)}%` : "NA"} />
          </div>
        ))}
      </div>
    </section>
  );
}

function CashFlowAndStress({ detail }: { detail: AdminApplicationDetail }) {
  const forecast = detail.forecast;
  const chart = [
    { name: "P10", value: forecast?.p10_conservative ?? 0 },
    { name: "P50", value: forecast?.p50_expected ?? 0 },
    { name: "P90", value: forecast?.p90_optimistic ?? 0 },
  ];
  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="section-panel">
        <h2 className="text-xl font-bold">Cash Flow</h2>
        <p className="mt-1 text-sm text-[color:var(--muted)]">{forecast?.method ?? "Forecast unavailable"}</p>
        <div className="mt-4 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart}>
              <CartesianGrid stroke="#eaecf0" vertical={false} />
              <XAxis dataKey="name" />
              <YAxis tickFormatter={(value) => `₹${Math.round(Number(value) / 1000)}k`} />
              <Tooltip formatter={(value) => formatCurrency(Number(value))} />
              <Area dataKey="value" fill="#bfdbfe" stroke="#2563eb" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="section-panel">
        <h2 className="text-xl font-bold">Stress Resilience</h2>
        <div className="mt-4 grid gap-3">
          <Metric label="Stress probability" value={formatPercent(detail.stress_test?.stress_probability)} />
          <Metric label="Worst scenario" value={detail.stress_test?.worst_scenario ?? "Not available"} />
          <Metric label="Minimum buffer" value={formatCurrency(detail.stress_test?.minimum_remaining_cash_buffer)} />
        </div>
        {detail.stress_test?.scenario_results?.length ? (
          <div className="mt-4 grid gap-2">
            {detail.stress_test.scenario_results.map((scenario) => (
              <ValueLine
                key={String(scenario.scenario)}
                label={String(scenario.scenario).replaceAll("_", " ")}
                value={`${scenario.survived ? "Pass" : "Stress"} · ${formatCurrency(Number(scenario.minimum_remaining_cash_buffer ?? 0))}`}
              />
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function EnvelopeWorkbench({ candidates }: { candidates: RepaymentCandidate[] }) {
  const [selected, setSelected] = useState<RepaymentCandidate | null>(candidates[0] ?? null);
  const amounts = Array.from(new Set(candidates.map((item) => item.amount))).sort((a, b) => a - b);
  const tenures = Array.from(new Set(candidates.map((item) => item.tenure_months))).sort((a, b) => a - b);
  useEffect(() => {
    setSelected((current) => current ?? candidates[0] ?? null);
  }, [candidates]);
  if (!candidates.length) {
    return <section className="section-panel"><h2 className="text-xl font-bold">Repayment Envelope</h2><div className="mt-4 empty-state">Repayment envelope unavailable</div></section>;
  }
  return (
    <section className="section-panel">
      <h2 className="text-xl font-bold">Repayment Envelope</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="data-table min-w-[720px]">
          <thead>
            <tr>
              <th>Tenure</th>
              {amounts.map((amount) => <th key={amount}>{formatCurrency(amount)}</th>)}
            </tr>
          </thead>
          <tbody>
            {tenures.map((tenure) => (
              <tr key={tenure}>
                <td className="font-bold">{tenure} mo</td>
                {amounts.map((amount) => {
                  const candidate = candidates.find((item) => item.amount === amount && item.tenure_months === tenure);
                  const isSelected = selected?.amount === amount && selected.tenure_months === tenure;
                  return (
                    <td key={`${tenure}-${amount}`}>
                      {candidate ? <button className={`envelope-cell envelope-${candidate.classification.toLowerCase()} w-full text-left ${isSelected ? "ring-2 ring-[color:var(--info)]" : ""}`} type="button" onClick={() => setSelected(candidate)}>{candidate.classification}</button> : "NA"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <Metric label="EMI" value={formatCurrency(selected.estimated_emi)} />
          <Metric label="Projected buffer" value={formatCurrency(selected.minimum_projected_buffer)} />
          <Metric label="Stress" value={formatPercent(selected.stress_probability)} />
          <Metric label="Class" value={selected.classification} />
        </div>
      ) : null}
    </section>
  );
}

function AuditTimeline({ detail }: { detail: AdminApplicationDetail }) {
  return (
    <section className="section-panel">
      <h2 className="text-xl font-bold">Audit Timeline</h2>
      <div className="mt-4 grid gap-3">
        {detail.audit_history.map((log) => (
          <div className="grid gap-1 border-l-2 border-[color:var(--accent)] pl-4" key={log.id}>
            <div className="text-xs font-bold text-[color:var(--muted)]">{new Date(log.created_at).toLocaleString("en-IN")}</div>
            <div className="font-bold">{log.action.replaceAll("_", " ")}</div>
            {log.metadata?.override ? <div className="text-sm text-amber-800">Override: {String(log.metadata.override_reason ?? "reason recorded separately")}</div> : null}
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
              <p className="page-kicker">Application #{detail.application.id}</p>
              <h1 className="page-title">{detail.borrower.name}</h1>
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
                <div>{detail.application.borrower_segment?.replaceAll("_", " ") ?? "Borrower type not supplied"}</div>
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

          {detail.segment_analysis ? <SegmentFinancialPanel analysis={detail.segment_analysis} /> : null}

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
              <h2 className="mb-4 text-xl font-bold">Evidence Confidence</h2>
              <ConfidenceGauge score={detail.evidence_confidence.score} band={detail.evidence_confidence.band} />
            </div>
          </section>

          <BehavioralRiskBreakdown detail={detail} />
          <DataSourceCoverage detail={detail} />
          <GrokPanel explanation={grokExplanation} loading={loading} onGenerate={generateGrok} />

          <EnvelopeWorkbench candidates={detail.repayment_envelope?.all_evaluated_combinations ?? []} />
          <CashFlowAndStress detail={detail} />

          <section className="decision-panel section-panel">
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
            {decision === "APPROVE_REQUESTED" && detail.nadi_recommendation.decision !== "APPROVE" ? (
              <div className="notice mt-4 border-amber-200 bg-amber-50 text-amber-900">
                This is a material override of NADI. A clear officer justification is required.
              </div>
            ) : null}
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
            {error ? <div className="notice mt-4 border-red-200 bg-red-50 text-red-700">{error}</div> : null}
            <button className="btn-primary mt-5" disabled={loading} type="submit">{loading ? "Saving" : "Save Decision"}</button>
          </form>

          <AuditTimeline detail={detail} />

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
