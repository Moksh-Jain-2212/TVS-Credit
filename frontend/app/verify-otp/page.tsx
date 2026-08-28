"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { verifyOtp } from "@/lib/api";

function VerifyOtpForm() {
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState(search.get("email") ?? "");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const mockOtp = sessionStorage.getItem("nadi_mock_otp");
    if (mockOtp) {
      setOtp(mockOtp);
    }
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await verifyOtp(email, otp);
      sessionStorage.removeItem("nadi_mock_otp");
      router.push("/login");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "OTP verification failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="auth-panel" onSubmit={submit}>
      <p className="text-sm font-bold text-[color:var(--accent)]">TVS NADI</p>
      <h1 className="mt-2 text-3xl font-black">Verify OTP</h1>
      <div className="mt-6 grid gap-4">
        <label><span className="label">Email</span><input className="field" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label><span className="label">OTP</span><input className="field" inputMode="numeric" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value)} /></label>
      </div>
      {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      <button className="btn-primary mt-6 w-full" disabled={loading} type="submit">{loading ? "Verifying" : "Verify"}</button>
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
