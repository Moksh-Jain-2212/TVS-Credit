"use client";

import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ApplicationSummary, ProtectedRoute, formatCurrency, formatPercent } from "@/components/platform";
import ElectricBorder from "@/components/ElectricBorder";
import { useAuth } from "@/context/AuthContext";
import { askNadi, getPlatformApplication, type NadiAssistantResponse, type PlatformApplication, type SegmentAnalysis } from "@/lib/api";

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
  return (
    <section className="section-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="page-kicker">{analysis.borrower_segment_label}</p>
          <h2 className="text-xl font-bold">Income Assessment</h2>
        </div>
        <span className="badge badge-info">{analysis.borrower_segment.replaceAll("_", " ")}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{analysis.income_interpretation}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="metric-card"><div className="metric-label">Conservative Income</div><div className="metric-value">{formatCurrency(analysis.conservative_income)}</div></div>
        <div className="metric-card"><div className="metric-label">Sustainable Surplus</div><div className="metric-value">{formatCurrency(analysis.sustainable_monthly_surplus)}</div></div>
        {Object.entries(analysis.segment_specific_features).slice(0, 6).map(([key, value]) => (
          <div className="metric-card" key={key}>
            <div className="metric-label">{key.replaceAll("_", " ")}</div>
            <div className="metric-value">{formatMetricValue(key, value)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AskNadiPanel({ applicationId, token }: { applicationId: number; token: string }) {
  const [question, setQuestion] = useState("Why did NADI make this decision?");
  const [response, setResponse] = useState<NadiAssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(await askNadi(applicationId, question, token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ask NADI is unavailable right now.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="section-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="page-kicker">Generative AI explanation</p>
          <h2 className="text-xl font-bold">Ask NADI</h2>
        </div>
        {response ? <span className="badge badge-info">{response.provider === "xAI" ? "AI response" : "Guided response"}</span> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">Ask about your existing assessment, SAFE TO LEARN, or evidence. This assistant cannot change your application decision.</p>
      <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
        <input className="field flex-1" value={question} maxLength={500} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this assessment" />
        <button className="btn-primary" type="submit" disabled={loading}>{loading ? "Thinking" : "Ask NADI"}</button>
      </form>
      {error ? <div className="notice mt-4 border-red-200 bg-red-50 text-red-700">{error}</div> : null}
      {response ? (
        <div className="mt-4 rounded-xl border border-[color:var(--line)] bg-[#f8fafc] p-4">
          <p className="whitespace-pre-line text-sm leading-6">{response.answer}</p>
          <p className="mt-3 text-xs font-semibold text-[color:var(--muted)]">{response.disclaimer}</p>
        </div>
      ) : null}
    </section>
  );
}

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
          {application.latest_underwriting?.segment_analysis ? (
            <SegmentFinancialPanel analysis={application.latest_underwriting.segment_analysis} />
          ) : null}
          <section className="section-panel">
            <h2 className="text-xl font-bold">Decision</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="metric-card"><div className="metric-label">Requested</div><div className="metric-value">{formatCurrency(application.requested_amount)}</div></div>
              <div className="metric-card"><div className="metric-label">Recommended</div><div className="metric-value">{formatCurrency(application.latest_underwriting?.recommended_amount)}</div></div>
              <div className="metric-card"><div className="metric-label">Final admin approval</div><div className="metric-value">{formatCurrency(application.latest_admin_decision?.approved_amount)}</div></div>
            </div>
            {application.latest_underwriting?.borrower_explanation ? (
              <div className="mt-4 text-sm leading-6 text-[color:var(--muted)]">
                {Object.values(application.latest_underwriting.borrower_explanation).flat().filter(Boolean).slice(0, 5).join(" ")}
              </div>
            ) : null}
          </section>
          {application.latest_underwriting?.behavioral_risk ? (
            <section className="decision-panel section-panel">
              <h2 className="text-xl font-bold">Alternative-data Evidence</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="metric-card"><div className="metric-label">Alternative-data coverage</div><div className="metric-value">{formatPercent(application.latest_underwriting.behavioral_risk.behavioral_data_coverage)}</div></div>
                <div className="metric-card"><div className="metric-label">Alternative-data confidence</div><div className="metric-value">{Math.round(application.latest_underwriting.behavioral_risk.behavioral_assessment_confidence ?? 0)} / 100</div></div>
                <div className="metric-card"><div className="metric-label">Current Risk</div><div className="metric-value">{formatPercent(application.latest_underwriting.behavioral_risk.combined_risk_probability)}</div></div>
              </div>
            </section>
          ) : null}
          {application.latest_underwriting ? (
            <section className="section-panel">
              <h2 className="text-xl font-bold">NADI Underwriting</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <div className="metric-card"><div className="metric-label">Recommendation</div><div className="metric-value">{application.latest_underwriting.nadi_decision_state?.replaceAll("_", " ") ?? "Pending"}</div></div>
                <div className="metric-card"><div className="metric-label">Evidence confidence</div><div className="metric-value">{application.latest_underwriting.confidence_score ?? "Not available"} / 100</div></div>
                <div className="metric-card"><div className="metric-label">Safe Exposure</div><div className="metric-value">{formatCurrency(application.latest_underwriting.maximum_safe_exposure)}</div></div>
                <div className="metric-card"><div className="metric-label">Stress Probability</div><div className="metric-value">{formatPercent(application.latest_underwriting.stress_probability)}</div></div>
                <div className="metric-card"><div className="metric-label">Worst Stress</div><div className="metric-value">{application.latest_underwriting.worst_stress_scenario?.replaceAll("_", " ") ?? "Not available"}</div></div>
              </div>
            </section>
          ) : null}
          {accessToken ? <ElectricBorder color="#7df9ff" speed={1} chaos={0.12} thickness={2} style={{ borderRadius: 16 }}><AskNadiPanel applicationId={application.id} token={accessToken} /></ElectricBorder> : null}
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
