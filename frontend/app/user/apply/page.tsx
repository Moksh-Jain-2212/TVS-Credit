"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import {
  connectDemoFinancialProfile,
  createPlatformApplication,
  submitPlatformApplication,
  updatePlatformApplication,
  type PlatformApplication,
} from "@/lib/api";

const steps = ["Employment", "Loan Request", "Financials", "Demo Data", "Review", "Submit"];

export default function ApplyPage() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [application, setApplication] = useState<PlatformApplication | null>(null);
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

  async function next() {
    setLoading(true);
    setError(null);
    try {
      if (step <= 2) {
        await saveDraft();
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
          <div>
            <h2 className="text-xl font-bold">Connect Demo Bank Data</h2>
            <p className="mt-2 text-sm text-[color:var(--muted)]">PKDD_DEMO · mocked/demo financial connectivity</p>
            <button className="btn-primary mt-5" disabled={loading} type="button" onClick={connectDemo}>Connect Demo Bank Data</button>
          </div>
        ) : null}
        {step === 4 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(payload()).map(([key, value]) => <div className="metric-card" key={key}><div className="metric-label">{key.replaceAll("_", " ")}</div><div className="metric-value">{String(value)}</div></div>)}
            <div className="metric-card"><div className="metric-label">Financial Data</div><div className="metric-value">{application?.demo_financial_profile_connected ? "Demo bank data connected" : "Not connected"}</div></div>
          </div>
        ) : null}
        {step === 5 ? (
          <div>
            <h2 className="text-xl font-bold">Submit Application</h2>
            <p className="mt-2 text-sm text-[color:var(--muted)]">NADI underwriting will run against the connected PKDD demo evidence snapshot.</p>
          </div>
        ) : null}
        {message ? <div className="mt-4 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div> : null}
        {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        <div className="mt-6 flex flex-wrap justify-between gap-3">
          <button className="btn-secondary" disabled={loading || step === 0} type="button" onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</button>
          {step < 3 ? <button className="btn-primary" disabled={loading} type="button" onClick={next}>Next</button> : null}
          {step === 4 ? <button className="btn-primary" disabled={loading} type="button" onClick={() => setStep(5)}>Continue</button> : null}
          {step === 5 ? <button className="btn-primary" disabled={loading} type="submit">{loading ? "Submitting" : "Submit"}</button> : null}
        </div>
      </form>
    </ProtectedRoute>
  );
}
