"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { resendOtp, verifyOtp } from "@/lib/api";

function VerifyOtpForm() {
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState(search.get("email") ?? "");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(30);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      await verifyOtp(email, otp);
      setSuccess("Email verified. Redirecting to login.");
      router.push("/login");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "OTP verification failed");
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    setResending(true);
    setError(null);
    setSuccess(null);
    try {
      await resendOtp(email);
      setSuccess("A new verification code has been sent to your email.");
      setOtp("");
      setCooldown(30);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to resend OTP");
    } finally {
      setResending(false);
    }
  }

  function updateOtp(value: string) {
    setOtp(value.replace(/\D/g, "").slice(0, 6));
  }

  return (
    <form className="auth-panel" onSubmit={submit}>
      <p className="page-kicker">TVS NADI</p>
      <h1 className="page-title">Verify your email</h1>
      <p className="mt-4 text-sm leading-6 text-[color:var(--muted)]">
        We&apos;ve sent a 6-digit verification code to <span className="font-bold text-[color:var(--foreground)]">{email || "your email"}</span>. Enter the code below.
      </p>
      <div className="mt-6 grid gap-4">
        <label><span className="label">Email</span><input className="field" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>
          <span className="label">Verification Code</span>
          <input className="field otp-input" autoComplete="one-time-code" inputMode="numeric" maxLength={6} value={otp} onChange={(event) => updateOtp(event.target.value)} autoFocus placeholder="000000" />
        </label>
      </div>
      {error ? <div className="notice mt-4 border-red-200 bg-red-50 text-red-700">{error}</div> : null}
      {success ? <div className="notice mt-4 border-emerald-200 bg-emerald-50 text-emerald-800">{success}</div> : null}
      <button className="btn-primary mt-6 w-full" disabled={loading || otp.length !== 6} type="submit">{loading ? "Verifying" : "Verify Email"}</button>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-sm">
        <span className="text-[color:var(--muted)]">Didn&apos;t receive the code?</span>
        <button className="btn-secondary" disabled={resending || !email || cooldown > 0} type="button" onClick={resend}>
          {resending ? "Resending" : cooldown > 0 ? `Resend in ${cooldown}s` : "Resend OTP"}
        </button>
      </div>
    </form>
  );
}

export default function VerifyOtpPage() {
  return (
    <main className="page-center">
      <Suspense fallback={<div className="page-center">Loading</div>}>
        <VerifyOtpForm />
      </Suspense>
    </main>
  );
}
