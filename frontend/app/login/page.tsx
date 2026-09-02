"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import Lightfall from "@/components/Lightfall";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await login(email, password);
      router.push(user.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-hero hidden overflow-hidden p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <Lightfall />
        <Link href="/" className="relative z-10 text-xl font-black">TVS NADI</Link>
        <div className="relative z-10 max-w-xl">
          <div className="badge border-white/25 bg-white/10 text-white">Evidence-aware underwriting</div>
          <h1 className="mt-5 text-5xl font-black leading-tight">Risk is not the same as uncertainty.</h1>
          <p className="mt-5 text-lg leading-8 text-slate-100">Review adaptive recommendations, behavioral evidence, and safe-to-learn credit paths in one governed workspace.</p>
        </div>
        <div className="relative z-10 grid grid-cols-3 gap-3 text-sm text-slate-200">
          <div className="hero-stat">Repayment risk</div>
          <div className="hero-stat">Capacity</div>
          <div className="hero-stat">Evidence confidence</div>
        </div>
      </section>
      <section className="grid place-items-center p-5">
        <form className="auth-panel" onSubmit={submit}>
          <Link href="/" className="mb-8 block text-lg font-black lg:hidden">TVS NADI</Link>
          <p className="page-kicker">Welcome back</p>
          <h1 className="page-title">Sign in to NADI</h1>
          <div className="mt-6 space-y-4">
            <label><span className="label">Email</span><input className="field" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
            <label><span className="label">Password</span><input className="field" autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          </div>
          {error ? <div className="notice mt-4 border-red-200 bg-red-50 text-red-700">{error}</div> : null}
          <button className="btn-primary mt-6 w-full" disabled={loading} type="submit">{loading ? "Signing in" : "Sign in"}</button>
          <p className="mt-4 text-sm text-[color:var(--muted)]">New borrower? <Link className="font-bold text-[color:var(--accent)]" href="/signup">Create an account</Link></p>
        </form>
      </section>
    </main>
  );
}
