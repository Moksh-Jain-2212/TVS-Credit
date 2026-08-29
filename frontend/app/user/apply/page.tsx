"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import {
  connectDemoFinancialProfile,
  connectMockAlternativeData,
  createPlatformApplication,
  getAlternativeDataStatus,
  grantAlternativeDataConsent,
  refreshAlternativeData,
  revokeAlternativeDataConsent,
  submitPlatformApplication,
  updatePlatformApplication,
  type AlternativeDataStatus,
  type PlatformApplication,
} from "@/lib/api";

const steps = ["Employment", "Loan Request", "Financials", "Evidence", "Review", "Submit"];

export default function ApplyPage() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [application, setApplication] = useState<PlatformApplication | null>(null);
  const [alternativeData, setAlternativeData] = useState<AlternativeDataStatus | null>(null);
  const [form, setForm] = useState({
    requested_amount: "100000",
    requested_tenure: "12",
    loan_purpose: "Two wheeler purchase",
    employment_type: "salaried",
    declared_monthly_income: "55000",
    declared_monthly_expenses: "22000",
    existing_monthly_emi: "0",
  });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function payload() {
    return {
      requested_amount: Number(form.requested_amount),
      requested_tenure: Number(form.requested_tenure),
      loan_purpose: form.loan_purpose,
      employment_type: form.employment_type,
      declared_monthly_income: Number(form.declared_monthly_income),
      declared_monthly_expenses: Number(form.declared_monthly_expenses),
      existing_monthly_emi: Number(form.existing_monthly_emi),
    };
  }

  async function saveDraft() {
    if (!accessToken) return null;
    const saved = application
      ? await updatePlatformApplication(application.id, payload(), accessToken)
      : await createPlatformApplication(payload(), accessToken);
    setApplication(saved);
    return saved;
  }

  async function loadAlternativeData(applicationId: number) {
    if (!accessToken) return null;
    const status = await getAlternativeDataStatus(applicationId, accessToken);
    setAlternativeData(status);
    return status;
  }

  async function next() {
    setLoading(true);
    setError(null);
    try {
      if (step <= 2) {
        const saved = await saveDraft();
        if (saved && step === 2) {
          await loadAlternativeData(saved.id);
        }
      }
      setStep((value) => Math.min(steps.length - 1, value + 1));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save application");
    } finally {
      setLoading(false);
    }
  }

  async function connectDemo() {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const saved = await saveDraft();
      if (!saved) return;
      const response = await connectDemoFinancialProfile(saved.id, accessToken);
      setMessage(String(response.label));
      setApplication({ ...saved, demo_financial_profile_connected: true, financial_data_source: "PKDD_DEMO" });
      setStep(4);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Demo connection failed");
    } finally {
      setLoading(false);
    }
  }

  async function connectSource(sourceType: string) {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const saved = await saveDraft();
      if (!saved) return;
      const current = alternativeData?.sources.find((source) => source.source_type === sourceType);
      if (current?.consent_status !== "GRANTED") {
        await grantAlternativeDataConsent(saved.id, sourceType, accessToken);
      }
      await connectMockAlternativeData(saved.id, sourceType, accessToken);
      const status = await loadAlternativeData(saved.id);
      setMessage(`${sourceType} behavioral evidence connected`);
      if (status?.readiness.ready) {
        setStep(4);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Source connection failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSource(sourceType: string) {
    if (!accessToken || !application) return;
    setLoading(true);
    setError(null);
    try {
      await refreshAlternativeData(application.id, sourceType, accessToken);
      await loadAlternativeData(application.id);
      setMessage(`${sourceType} evidence refreshed`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  }

  async function revokeSource(sourceType: string) {
    if (!accessToken || !application) return;
    setLoading(true);
    setError(null);
    try {
      await revokeAlternativeDataConsent(application.id, sourceType, accessToken);
      await loadAlternativeData(application.id);
      setMessage(`${sourceType} consent revoked`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to revoke consent");
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken || !application) return;
    setLoading(true);
    setError(null);
    try {
      const response = await submitPlatformApplication(application.id, accessToken);
      router.push(`/user/applications/${response.application.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ProtectedRoute role="USER">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-[color:var(--accent)]">Loan Application</p>
          <h1 className="text-3xl font-black">Apply for Loan</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {steps.map((label, index) => <span className={`badge ${index === step ? "badge-good" : "badge-neutral"}`} key={label}>{label}</span>)}
        </div>
      </div>
      <form className="mt-6 section-panel" onSubmit={submit}>
        {step === 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <label><span className="label">Employment Type</span><input className="field" value={form.employment_type} onChange={(event) => setForm({ ...form, employment_type: event.target.value })} /></label>
            <label><span className="label">Loan Purpose</span><input className="field" value={form.loan_purpose} onChange={(event) => setForm({ ...form, loan_purpose: event.target.value })} /></label>
          </div>
        ) : null}
        {step === 1 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <label><span className="label">Requested Amount</span><input className="field" inputMode="numeric" value={form.requested_amount} onChange={(event) => setForm({ ...form, requested_amount: event.target.value })} /></label>
            <label><span className="label">Requested Tenure</span><input className="field" inputMode="numeric" value={form.requested_tenure} onChange={(event) => setForm({ ...form, requested_tenure: event.target.value })} /></label>
          </div>
        ) : null}
        {step === 2 ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <label><span className="label">Monthly Income</span><input className="field" inputMode="numeric" value={form.declared_monthly_income} onChange={(event) => setForm({ ...form, declared_monthly_income: event.target.value })} /></label>
            <label><span className="label">Monthly Expenses</span><input className="field" inputMode="numeric" value={form.declared_monthly_expenses} onChange={(event) => setForm({ ...form, declared_monthly_expenses: event.target.value })} /></label>
            <label><span className="label">Existing EMI</span><input className="field" inputMode="numeric" value={form.existing_monthly_emi} onChange={(event) => setForm({ ...form, existing_monthly_emi: event.target.value })} /></label>
          </div>
        ) : null}
        {step === 3 ? (
          <div className="grid gap-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold">Behavioral Financial Evidence</h2>
                <p className="mt-2 text-sm text-[color:var(--muted)]">Connect at least one consented source. Mock connectors use normalized aggregate records for local testing.</p>
              </div>
              <div className={alternativeData?.readiness.ready ? "badge badge-good" : "badge badge-warn"}>
                {alternativeData?.readiness.connected_source_count ?? 0} connected
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {(alternativeData?.sources ?? []).map((source) => (
                <div className="item-card flex min-h-[250px] flex-col justify-between" key={source.source_type}>
                  <div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="font-bold">{source.label}</h3>
                      <span className={source.active ? "badge badge-good" : "badge badge-neutral"}>{source.active ? "Connected" : "Not connected"}</span>
                    </div>
                    <p className="mt-3 text-sm text-[color:var(--muted)]">{source.requested}</p>
                    <p className="mt-3 text-sm">{source.why}</p>
                    <p className="mt-3 text-xs text-[color:var(--muted)]">{source.excluded}</p>
                    {source.quality_score !== null ? <p className="mt-3 text-xs font-bold">Quality {Math.round(source.quality_score * 100)}%</p> : null}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button className="btn-primary" disabled={loading} type="button" onClick={() => connectSource(source.source_type)}>
                      {source.active ? "Reconnect Mock" : "Connect Mock"}
                    </button>
                    {source.active ? <button className="btn-secondary" disabled={loading} type="button" onClick={() => refreshSource(source.source_type)}>Refresh</button> : null}
                    {source.consent_status === "GRANTED" ? <button className="btn-secondary" disabled={loading} type="button" onClick={() => revokeSource(source.source_type)}>Revoke</button> : null}
                  </div>
                </div>
              ))}
            </div>
            <div className="empty-state">
              {alternativeData?.readiness.message ?? "Save the application details to load evidence sources."}
              {alternativeData?.readiness.ready ? ` Coverage ${Math.round(alternativeData.readiness.behavioral_data_coverage * 100)}%, confidence ${Math.round(alternativeData.readiness.behavioral_assessment_confidence)}.` : ""}
            </div>
            <div>
              <button className="btn-secondary" disabled={loading} type="button" onClick={connectDemo}>Use Demo Bank Data</button>
            </div>
          </div>
        ) : null}
        {step === 4 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(payload()).map(([key, value]) => <div className="metric-card" key={key}><div className="metric-label">{key.replaceAll("_", " ")}</div><div className="metric-value">{String(value)}</div></div>)}
            <div className="metric-card"><div className="metric-label">Financial Data</div><div className="metric-value">{application?.demo_financial_profile_connected ? "Demo bank data connected" : `${alternativeData?.readiness.connected_source_count ?? 0} behavioral sources`}</div></div>
          </div>
        ) : null}
        {step === 5 ? (
          <div>
            <h2 className="text-xl font-bold">Submit Application</h2>
            <p className="mt-2 text-sm text-[color:var(--muted)]">NADI underwriting will run against connected evidence and keep behavioral risk separate from historical model risk.</p>
          </div>
        ) : null}
        {message ? <div className="mt-4 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div> : null}
        {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        <div className="mt-6 flex flex-wrap justify-between gap-3">
          <button className="btn-secondary" disabled={loading || step === 0} type="button" onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</button>
          {step < 3 ? <button className="btn-primary" disabled={loading} type="button" onClick={next}>Next</button> : null}
          {step === 3 ? <button className="btn-primary" disabled={loading || (!alternativeData?.readiness.ready && !application?.demo_financial_profile_connected)} type="button" onClick={() => setStep(4)}>Review</button> : null}
          {step === 4 ? <button className="btn-primary" disabled={loading} type="button" onClick={() => setStep(5)}>Continue</button> : null}
          {step === 5 ? <button className="btn-primary" disabled={loading} type="submit">{loading ? "Submitting" : "Submit"}</button> : null}
        </div>
      </form>
    </ProtectedRoute>
  );
}
