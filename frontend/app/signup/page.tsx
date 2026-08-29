"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { register } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await register(form);
      router.push(`/verify-otp?email=${encodeURIComponent(form.email)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-hero hidden p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <Link href="/" className="text-xl font-black">TVS NADI</Link>
        <div className="max-w-xl">
          <div className="badge border-white/25 bg-white/10 text-white">Borrower journey</div>
          <h1 className="mt-5 text-5xl font-black leading-tight">Build eligibility with evidence you control.</h1>
          <p className="mt-5 text-lg leading-8 text-slate-100">Connect privacy-conscious financial evidence and see a clear, respectful path through application, analysis, review, and decision.</p>
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm text-slate-200">
          <div className="hero-stat">No SMS content</div>
          <div className="hero-stat">No contacts</div>
          <div className="hero-stat">No exact GPS trails</div>
        </div>
      </section>
      <section className="grid place-items-center p-5">
        <form className="auth-panel" onSubmit={submit}>
          <Link href="/" className="mb-8 block text-lg font-black lg:hidden">TVS NADI</Link>
          <p className="page-kicker">Borrower signup</p>
          <h1 className="page-title">Create your account</h1>
          <div className="mt-6 grid gap-4">
            <label><span className="label">Name</span><input className="field" autoComplete="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label><span className="label">Email</span><input className="field" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
            <label><span className="label">Phone</span><input className="field" autoComplete="tel" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
            <label><span className="label">Password</span><input className="field" autoComplete="new-password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
          </div>
          {error ? <div className="notice mt-4 border-red-200 bg-red-50 text-red-700">{error}</div> : null}
          <button className="btn-primary mt-6 w-full" disabled={loading} type="submit">{loading ? "Creating account" : "Create account"}</button>
          <p className="mt-4 text-sm text-[color:var(--muted)]">Already registered? <Link className="font-bold text-[color:var(--accent)]" href="/login">Login</Link></p>
        </form>
      </section>
    </main>
  );
}
