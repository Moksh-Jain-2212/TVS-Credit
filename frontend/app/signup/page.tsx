"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { register } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [mockOtp, setMockOtp] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await register(form);
      if (response.otp_delivery.development_otp) {
        setMockOtp(response.otp_delivery.development_otp);
        sessionStorage.setItem("nadi_mock_otp", response.otp_delivery.development_otp);
      }
      router.push(`/verify-otp?email=${encodeURIComponent(form.email)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-center">
      <form className="auth-panel" onSubmit={submit}>
        <p className="text-sm font-bold text-[color:var(--accent)]">TVS NADI</p>
        <h1 className="mt-2 text-3xl font-black">Borrower Signup</h1>
        <div className="mt-6 grid gap-4">
          <label><span className="label">Name</span><input className="field" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
          <label><span className="label">Email</span><input className="field" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          <label><span className="label">Phone</span><input className="field" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
          <label><span className="label">Password</span><input className="field" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
        </div>
        {mockOtp ? <div className="mt-4 border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">OTP delivery: MOCK_CONSOLE · {mockOtp}</div> : null}
        {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        <button className="btn-primary mt-6 w-full" disabled={loading} type="submit">{loading ? "Creating account" : "Create account"}</button>
        <p className="mt-4 text-sm text-[color:var(--muted)]">
          Already registered? <Link className="font-bold text-[color:var(--accent)]" href="/login">Login</Link>
        </p>
      </form>
    </main>
  );
}
