"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  analyzeApplication,
  getBorrowers,
  runDemoSimulation,
  type AdaptiveObservation,
  type AnalysisResponse,
  type BorrowerSummary,
  type DemoAction,
  type DemoSimulationResponse,
  type RepaymentCandidate,
} from "@/lib/api";

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCompactCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  return `${Math.round(value * 100)}%`;
}

function safeNumber(value: number | null | undefined): number {
  return value === null || value === undefined || Number.isNaN(value) ? 0 : value;
}

function formatTooltipCurrency(value: unknown): string {
  const numericValue = typeof value === "number" ? value : Number(value);
  return formatCurrency(Number.isNaN(numericValue) ? 0 : numericValue);
}

function signedCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatCurrency(value)}`;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-[color:var(--line)] bg-[color:var(--panel)] p-4">
      <div className="metric-label">{label}</div>
      <div className="metric-value mt-1">{value}</div>
    </div>
  );
}

function PulseGauge({ label, value }: { label: string; value: number | null | undefined }) {
  const normalized = Math.max(0, Math.min(100, safeNumber(value) * 100));
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-semibold">{label}</span>
        <span className="text-[color:var(--muted)]">{formatPercent(value)}</span>
      </div>
      <div className="mt-2 h-2 bg-[#e5e7eb]">
        <div className="h-2 bg-[color:var(--accent)]" style={{ width: `${normalized}%` }} />
      </div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[color:var(--line)] py-3 last:border-b-0">
      <span className="text-sm text-[color:var(--muted)]">{label}</span>
      <span className="max-w-[56%] text-right text-sm font-semibold">{value}</span>
    </div>
  );
}

function candidateKey(candidate: RepaymentCandidate): string {
  return `${candidate.amount}-${candidate.tenure_months}`;
}

function classificationClass(classification: RepaymentCandidate["classification"], selected: boolean): string {
  const base = "flex h-16 w-full flex-col items-center justify-center border text-xs font-bold transition";
  const selectedRing = selected ? " outline outline-2 outline-offset-2 outline-[color:var(--foreground)]" : "";
  if (classification === "SAFE") {
    return `${base} border-emerald-300 bg-emerald-100 text-emerald-900 hover:bg-emerald-200${selectedRing}`;
  }
  if (classification === "BORDERLINE") {
    return `${base} border-amber-300 bg-amber-100 text-amber-900 hover:bg-amber-200${selectedRing}`;
  }
  return `${base} border-red-200 bg-red-50 text-red-900 hover:bg-red-100${selectedRing}`;
}

function eventLabel(event: string): string {
  return event.replaceAll("_", " ");
}

function JourneyStep({
  eyebrow,
  title,
  detail,
  tone = "neutral",
}: {
  eyebrow: string;
  title: string;
  detail: string;
  tone?: "neutral" | "good" | "warning";
}) {
  const toneClass =
    tone === "good"
      ? "border-emerald-300 bg-emerald-50 text-emerald-950"
      : tone === "warning"
        ? "border-amber-300 bg-amber-50 text-amber-950"
        : "border-[color:var(--line)] bg-white";
  return (
    <div className={`min-h-28 border p-4 ${toneClass}`}>
      <div className="text-xs font-semibold uppercase text-[color:var(--muted)]">{eyebrow}</div>
      <div className="mt-2 text-lg font-bold">{title}</div>
      <div className="mt-2 text-sm text-[color:var(--muted)]">{detail}</div>
    </div>
  );
}

function observationTone(observation: AdaptiveObservation): "good" | "warning" | "neutral" {
  if (observation.event === "on_time") {
    return "good";
  }
  if (observation.event === "missed" || observation.decision_state === "NOT_CURRENTLY_AFFORDABLE") {
    return "warning";
  }
  return "neutral";
}

const DEMO_ACTIONS: { action: DemoAction; label: string }[] = [
  { action: "on_time", label: "Simulate on-time repayment" },
  { action: "late", label: "Simulate late repayment" },
  { action: "missed", label: "Simulate missed repayment" },
  { action: "income_shock_20", label: "Apply -20% income shock" },
  { action: "emergency_expense", label: "Apply emergency expense" },
  { action: "additional_evidence", label: "Add additional evidence" },
];

function DemoSimulator({ applicationId }: { applicationId: number }) {
  const [result, setResult] = useState<DemoSimulationResponse | null>(null);
  const [runningAction, setRunningAction] = useState<DemoAction | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResult(null);
    setError(null);
    setRunningAction(null);
  }, [applicationId]);

  async function runAction(action: DemoAction) {
    setRunningAction(action);
    setError(null);
    try {
      setResult(await runDemoSimulation(applicationId, action));
    } catch (caught: unknown) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Demo simulation failed");
    } finally {
      setRunningAction(null);
    }
  }

  return (
    <section className="border border-[color:var(--line)] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[color:var(--accent)]">Demo Simulator</p>
          <h2 className="text-xl font-bold">Mocked Events, Real NADI Recalculation</h2>
        </div>
        <button
          className="border border-[color:var(--line)] px-3 py-2 text-sm font-semibold hover:bg-[#f8fafc]"
          type="button"
          onClick={() => {
            setResult(null);
            setError(null);
          }}
        >
          Reset Demo
        </button>
      </div>

      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {DEMO_ACTIONS.map((item) => (
          <button
            key={item.action}
            className="min-h-12 border border-[color:var(--line)] px-3 py-2 text-left text-sm font-semibold hover:border-[color:var(--accent)] hover:bg-[#f8fafc] disabled:cursor-wait disabled:opacity-60"
            type="button"
            disabled={runningAction !== null}
            onClick={() => runAction(item.action)}
          >
            {runningAction === item.action ? "Running..." : item.label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="mt-4 border border-red-200 bg-red-50 px-4 py-3 text-sm text-[color:var(--danger)]">{error}</div>
      ) : null}

      {result ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1.15fr]">
          <div className="border border-[color:var(--line)] p-4">
            <div className="text-sm text-[color:var(--muted)]">Last demo event</div>
            <div className="mt-1 text-lg font-bold">{DEMO_ACTIONS.find((item) => item.action === result.action)?.label}</div>
            <div className="mt-3 text-sm font-semibold text-[color:var(--warning)]">Mock simulation</div>
            <div className="mt-3 text-sm text-[color:var(--muted)]">{result.result.reason}</div>
          </div>
          <div className="border border-[color:var(--line)] p-4">
            <div className="grid gap-x-5 sm:grid-cols-2">
              <KeyValue label="Decision" value={result.result.decision_state ?? "Not available"} />
              <KeyValue label="Safe exposure" value={formatCurrency(result.result.maximum_safe_exposure)} />
              <KeyValue label="Recommended" value={formatCurrency(result.result.recommended_amount)} />
              <KeyValue label="Recommended EMI" value={formatCurrency(result.result.recommended_emi)} />
              <KeyValue label="Confidence" value={result.result.updated_confidence_score?.toString() ?? "Not available"} />
              <KeyValue label="Risk" value={formatPercent(result.result.updated_risk_probability)} />
              <KeyValue label="Stress survival" value={formatPercent(result.result.stress_survival)} />
              <KeyValue label="Buffer" value={formatCurrency(result.result.minimum_remaining_cash_buffer)} />
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function AdaptiveCreditPathJourney({ analysis }: { analysis: AnalysisResponse }) {
  const path = analysis.credit_path;
  const observations = path.simulated_observations;
  const hasStarter = path.starter_credit_eligible && path.starter_amount > 0;
  const finalExposure = observations.at(-1)?.maximum_safe_exposure ?? path.final_recommended_amount;

  return (
    <section className="border border-[color:var(--line)] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[color:var(--accent)]">Adaptive Credit Path</p>
          <h2 className="text-xl font-bold">Re-underwriting Journey</h2>
        </div>
        <div className="border border-[color:var(--line)] px-3 py-2 text-sm font-semibold">
          {hasStarter ? "Starter path available" : "No starter path"}
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <JourneyStep
          eyebrow="Requested"
          title={formatCurrency(analysis.decision.requested_amount)}
          detail={`Current decision: ${analysis.decision.decision_state}`}
          tone={analysis.decision.decision_state === "SAFE_TO_LEARN" ? "good" : "warning"}
        />
        <JourneyStep
          eyebrow="Starter Exposure"
          title={hasStarter ? formatCurrency(path.starter_amount) : "Not available"}
          detail={hasStarter ? `${path.starter_tenure ?? "N/A"} mo, EMI ${formatCurrency(path.starter_emi)}` : path.starter_reason}
          tone={hasStarter ? "good" : "warning"}
        />
        <JourneyStep
          eyebrow="Re-underwriting"
          title={path.final_decision ?? analysis.decision.decision_state}
          detail={`Updated safe exposure: ${formatCurrency(finalExposure)}`}
          tone={path.final_decision === "SAFE_TO_LEARN" || path.final_decision === "APPROVE" ? "good" : "warning"}
        />
        <JourneyStep
          eyebrow="Guardrail"
          title="No automatic increase"
          detail="Every new repayment observation must be re-underwritten before exposure changes."
        />
      </div>

      <div className="mt-5 border-t border-[color:var(--line)] pt-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-bold">Repayment Observations</h3>
          <span className="text-sm text-[color:var(--muted)]">Initial confidence {analysis.financial_profile.confidence_score}</span>
        </div>
        {observations.length ? (
          <div className="grid gap-3 lg:grid-cols-3">
            {observations.map((observation) => (
              <div key={observation.event} className="border border-[color:var(--line)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-bold capitalize">{eventLabel(observation.event)}</span>
                  <span
                    className={`border px-2 py-1 text-xs font-semibold ${
                      observationTone(observation) === "good"
                        ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                        : observationTone(observation) === "warning"
                          ? "border-amber-300 bg-amber-50 text-amber-900"
                          : "border-[color:var(--line)] text-[color:var(--muted)]"
                    }`}
                  >
                    Simulated
                  </span>
                </div>
                <div className="mt-3">
                  <KeyValue label="Confidence" value={`${observation.updated_confidence_score}`} />
                  <KeyValue label="Risk" value={formatPercent(observation.updated_risk_probability)} />
                  <KeyValue label="Safe exposure" value={formatCurrency(observation.maximum_safe_exposure)} />
                  <KeyValue label="Decision" value={observation.decision_state} />
                </div>
                <div className="mt-3 text-sm text-[color:var(--muted)]">{observation.decision_reasons[0] ?? "re-underwritten after observation"}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-[color:var(--line)] bg-[#f8fafc] p-4 text-sm text-[color:var(--muted)]">
            No simulated starter-credit observations exist for this application.
          </div>
        )}
      </div>
    </section>
  );
}

function RepaymentEnvelopeHero({ analysis }: { analysis: AnalysisResponse }) {
  const candidates = analysis.repayment_envelope.all_evaluated_combinations;
  const defaultCandidate = useMemo(() => {
    const recommended = candidates.find(
      (candidate) =>
        candidate.amount === analysis.repayment_envelope.recommended_amount &&
        candidate.tenure_months === analysis.repayment_envelope.recommended_tenure,
    );
    return recommended ?? candidates[0] ?? null;
  }, [analysis.repayment_envelope.recommended_amount, analysis.repayment_envelope.recommended_tenure, candidates]);
  const [selectedKey, setSelectedKey] = useState(() => (defaultCandidate ? candidateKey(defaultCandidate) : ""));
  const selectedCandidate = candidates.find((candidate) => candidateKey(candidate) === selectedKey) ?? defaultCandidate;
  const amounts = useMemo(
    () => Array.from(new Set(candidates.map((candidate) => candidate.amount))).sort((first, second) => first - second),
    [candidates],
  );
  const tenures = useMemo(
    () => Array.from(new Set(candidates.map((candidate) => candidate.tenure_months))).sort((first, second) => first - second),
    [candidates],
  );
  const counts = candidates.reduce(
    (accumulator, candidate) => {
      accumulator[candidate.classification] += 1;
      return accumulator;
    },
    { SAFE: 0, BORDERLINE: 0, UNSAFE: 0 },
  );

  if (!selectedCandidate) {
    return null;
  }

  return (
    <section className="border border-[color:var(--line)] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[color:var(--accent)]">Repayment Envelope</p>
          <h2 className="text-xl font-bold">Loan Amount x Tenure</h2>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className="border border-emerald-300 bg-emerald-100 px-2 py-1 text-emerald-900">SAFE {counts.SAFE}</span>
          <span className="border border-amber-300 bg-amber-100 px-2 py-1 text-amber-900">BORDERLINE {counts.BORDERLINE}</span>
          <span className="border border-red-200 bg-red-50 px-2 py-1 text-red-900">UNSAFE {counts.UNSAFE}</span>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_300px]">
        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            <div className="grid gap-2" style={{ gridTemplateColumns: `112px repeat(${tenures.length}, minmax(88px, 1fr))` }}>
              <div />
              {tenures.map((tenure) => (
                <div key={tenure} className="py-2 text-center text-sm font-bold">
                  {tenure} mo
                </div>
              ))}
              {amounts.map((amount) => (
                <div key={amount} className="contents">
                  <div className="flex h-16 items-center text-sm font-bold">{formatCurrency(amount)}</div>
                  {tenures.map((tenure) => {
                    const candidate = candidates.find((item) => item.amount === amount && item.tenure_months === tenure);
                    if (!candidate) {
                      return <div key={`${amount}-${tenure}`} className="h-16 border border-[color:var(--line)] bg-[#f8fafc]" />;
                    }
                    const selected = selectedCandidate ? candidateKey(candidate) === candidateKey(selectedCandidate) : false;
                    return (
                      <button
                        key={candidateKey(candidate)}
                        className={classificationClass(candidate.classification, selected)}
                        type="button"
                        onClick={() => setSelectedKey(candidateKey(candidate))}
                      >
                        <span>{candidate.classification}</span>
                        <span className="mt-1 font-normal">{formatCurrency(candidate.estimated_emi)}</span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>

        <aside className="border border-[color:var(--line)] p-4">
          <div className="text-sm text-[color:var(--muted)]">Selected combination</div>
          <div className="mt-1 text-lg font-bold">
            {formatCurrency(selectedCandidate.amount)} over {selectedCandidate.tenure_months} mo
          </div>
          <div className="mt-4">
            <KeyValue label="Classification" value={selectedCandidate.classification} />
            <KeyValue label="Estimated EMI" value={formatCurrency(selectedCandidate.estimated_emi)} />
            <KeyValue label="Stress survival" value={formatPercent(1 - selectedCandidate.stress_probability)} />
            <KeyValue label="Minimum buffer" value={formatCurrency(selectedCandidate.minimum_projected_buffer)} />
            <KeyValue label="EMI / cash flow" value={`${selectedCandidate.emi_to_expected_cash_flow.toFixed(2)}x`} />
          </div>
          <div className="mt-4 border-t border-[color:var(--line)] pt-4 text-sm font-semibold">
            {selectedCandidate.classification_reasons[0] ?? "classification follows repayment envelope policy"}
          </div>
        </aside>
      </div>
    </section>
  );
}

function FinancialPulse({ analysis }: { analysis: AnalysisResponse }) {
  const profile = analysis.financial_profile;
  const risk = analysis.decision.loan_officer_explanation.risk;
  const capacity = analysis.decision.loan_officer_explanation.capacity;
  const riskProbability = risk?.probability ?? 0;
  const surplus = profile.mean_monthly_net_cash_flow;
  const cashFlowBars = [
    { label: "Inflow", amount: safeNumber(profile.mean_monthly_inflow), color: "#0f766e" },
    { label: "Expenses", amount: safeNumber(profile.mean_monthly_outflow), color: "#b45309" },
    { label: "Surplus", amount: safeNumber(surplus), color: surplus >= 0 ? "#2563eb" : "#b91c1c" },
  ];
  const cashFlowTrend = [
    { label: "Observed", amount: safeNumber(profile.mean_monthly_net_cash_flow) },
    { label: "P10", amount: safeNumber(analysis.forecast.p10_conservative) },
    { label: "P50", amount: safeNumber(analysis.forecast.p50_expected) },
    { label: "P90", amount: safeNumber(analysis.forecast.p90_optimistic) },
  ];
  const incomeTrend = profile.phase7_income_trend ?? profile.income_trend;
  const bureauStatus = profile.bureau_available ? "Available" : "Not available";

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[color:var(--accent)]">Financial Pulse</p>
          <h2 className="text-xl font-bold">Application {analysis.application_id}</h2>
        </div>
        <div className="border border-[color:var(--line)] bg-white px-4 py-3 text-sm">
          <span className="text-[color:var(--muted)]">Requested loan</span>
          <div className="text-lg font-bold">{formatCurrency(analysis.decision.requested_amount)}</div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Bureau Availability" value={bureauStatus} />
        <Metric label="Monthly Inflow" value={formatCurrency(profile.mean_monthly_inflow)} />
        <Metric label="Monthly Expenses" value={formatCurrency(profile.mean_monthly_outflow)} />
        <Metric label="Monthly Surplus" value={signedCurrency(profile.mean_monthly_net_cash_flow)} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="border border-[color:var(--line)] bg-white p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-bold">Cash-Flow Shape</h3>
              <p className="text-sm text-[color:var(--muted)]">
                {profile.months_of_history} months observed, {analysis.forecast.history_months} months used for forecast
              </p>
            </div>
            <div className="text-right text-sm">
              <div className="text-[color:var(--muted)]">Cash-flow trend</div>
              <div className="font-semibold">{signedCurrency(incomeTrend)}</div>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="h-64 min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cashFlowBars} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={(value: number) => formatCompactCurrency(value)} width={54} />
                  <Tooltip formatter={formatTooltipCurrency} />
                  <ReferenceLine y={0} stroke="#64748b" />
                  <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
                    {cashFlowBars.map((entry) => (
                      <Cell key={entry.label} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="h-64 min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cashFlowTrend} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#e5e7eb" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={(value: number) => formatCompactCurrency(value)} width={54} />
                  <Tooltip formatter={formatTooltipCurrency} />
                  <ReferenceLine y={0} stroke="#64748b" />
                  <Line type="monotone" dataKey="amount" stroke="#2563eb" strokeWidth={3} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          <div className="border border-[color:var(--line)] bg-white p-5">
            <h3 className="font-bold">Evidence Confidence</h3>
            <div className="mt-4 flex items-baseline justify-between gap-3">
              <span className="text-3xl font-bold">{profile.confidence_score}</span>
              <span className="text-sm font-semibold uppercase text-[color:var(--accent)]">{profile.confidence_band}</span>
            </div>
            <div className="mt-4 h-2 bg-[#e5e7eb]">
              <div className="h-2 bg-[color:var(--accent)]" style={{ width: `${Math.max(0, Math.min(100, profile.confidence_score))}%` }} />
            </div>
            <div className="mt-4 text-sm text-[color:var(--muted)]">{profile.bureau_status.replaceAll("_", " ")}</div>
          </div>

          <div className="border border-[color:var(--line)] bg-white p-5">
            <h3 className="font-bold">Income Stability</h3>
            <div className="mt-4 space-y-4">
              <PulseGauge label="Income stability" value={profile.income_stability_score} />
              <PulseGauge label="Cash-flow stability" value={profile.cash_flow_stability_score} />
              <PulseGauge label="Positive months" value={profile.positive_cash_flow_month_ratio} />
            </div>
            <div className="mt-4 text-sm text-[color:var(--muted)]">{profile.stability_history_status?.replaceAll("_", " ") ?? "Not available"}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="border border-[color:var(--line)] bg-white p-5">
          <h3 className="font-bold">Risk</h3>
          <div className="mt-3">
            <KeyValue label="Repayment risk" value={formatPercent(riskProbability)} />
            <KeyValue label="Risk band" value={risk?.band ?? "Not available"} />
            <KeyValue label="Worst stress scenario" value={analysis.stress_test.worst_scenario?.replaceAll("_", " ") ?? "Not available"} />
            <KeyValue label="Stress probability" value={formatPercent(analysis.stress_test.stress_probability)} />
          </div>
        </div>

        <div className="border border-[color:var(--line)] bg-white p-5">
          <h3 className="font-bold">Capacity</h3>
          <div className="mt-3">
            <KeyValue label="Safe exposure" value={formatCurrency(analysis.repayment_envelope.maximum_safe_exposure)} />
            <KeyValue label="Expected cash flow" value={formatCurrency(capacity?.expected_monthly_cash_flow)} />
            <KeyValue label="Conservative cash flow" value={formatCurrency(capacity?.conservative_monthly_cash_flow)} />
            <KeyValue label="Scheduled EMI" value={formatCurrency(capacity?.scheduled_payment)} />
          </div>
        </div>
      </div>
    </section>
  );
}

export function NadiDashboard() {
  const [borrowers, setBorrowers] = useState<BorrowerSummary[]>([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loadingBorrowers, setLoadingBorrowers] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBorrowers()
      .then((items) => {
        setBorrowers(items);
        setSelectedApplicationId(items[0]?.latest_loan_id ?? null);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Unable to load applicants");
      })
      .finally(() => setLoadingBorrowers(false));
  }, []);

  useEffect(() => {
    if (selectedApplicationId === null) {
      return;
    }
    setLoadingAnalysis(true);
    setError(null);
    analyzeApplication(selectedApplicationId)
      .then(setAnalysis)
      .catch((caught: unknown) => {
        setAnalysis(null);
        setError(caught instanceof Error ? caught.message : "Unable to analyze application");
      })
      .finally(() => setLoadingAnalysis(false));
  }, [selectedApplicationId]);

  const selectedBorrower = useMemo(
    () => borrowers.find((borrower) => borrower.latest_loan_id === selectedApplicationId),
    [borrowers, selectedApplicationId],
  );

  return (
    <main className="min-h-screen">
      <header className="border-b border-[color:var(--line)] bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-[color:var(--accent)]">TVS NADI</p>
            <h1 className="text-2xl font-bold">Adaptive Credit Path Engine</h1>
          </div>
          <div className="text-right text-sm text-[color:var(--muted)]">FastAPI connected</div>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-5 px-5 py-6 lg:grid-cols-[320px_1fr]">
        <aside className="border border-[color:var(--line)] bg-white p-4">
          <label className="text-sm font-semibold" htmlFor="applicant">
            Applicant
          </label>
          {loadingBorrowers ? (
            <div className="mt-3 text-sm text-[color:var(--muted)]">Loading applicants...</div>
          ) : (
            <select
              id="applicant"
              className="mt-3 w-full border border-[color:var(--line)] bg-white px-3 py-2"
              value={selectedApplicationId ?? ""}
              onChange={(event) => setSelectedApplicationId(Number(event.target.value))}
            >
              {borrowers.map((borrower) => (
                <option key={borrower.latest_loan_id} value={borrower.latest_loan_id}>
                  Account {borrower.account_id} - App {borrower.latest_loan_id}
                </option>
              ))}
            </select>
          )}

          {selectedBorrower ? (
            <div className="mt-5 space-y-3 text-sm">
              <div>
                <span className="text-[color:var(--muted)]">Latest decision</span>
                <div className="font-semibold">{selectedBorrower.latest_decision}</div>
              </div>
              <div>
                <span className="text-[color:var(--muted)]">Confidence</span>
                <div className="font-semibold">{selectedBorrower.latest_confidence_score}</div>
              </div>
            </div>
          ) : null}
        </aside>

        <section className="space-y-5">
          {error ? (
            <div className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-[color:var(--danger)]">
              {error}
            </div>
          ) : null}

          {loadingAnalysis ? (
            <div className="border border-[color:var(--line)] bg-white p-6 text-[color:var(--muted)]">
              Analyzing application...
            </div>
          ) : null}

          {analysis ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <Metric label="Decision" value={analysis.decision.decision_state} />
                <Metric label="Requested" value={formatCurrency(analysis.decision.requested_amount)} />
                <Metric label="Recommended" value={formatCurrency(analysis.decision.recommended_amount)} />
              </div>

              <RepaymentEnvelopeHero analysis={analysis} />

              <AdaptiveCreditPathJourney analysis={analysis} />

              <DemoSimulator applicationId={analysis.application_id} />

              <FinancialPulse analysis={analysis} />

              <div className="border border-[color:var(--line)] bg-white p-5">
                <h2 className="text-lg font-bold">Decision Reasons</h2>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-[color:var(--muted)]">
                  {analysis.decision.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            </>
          ) : null}
        </section>
      </section>
    </main>
  );
}
