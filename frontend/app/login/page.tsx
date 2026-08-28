"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "@/context/AuthContext";

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
    <main className="page-center">
      <form className="auth-panel" onSubmit={submit}>
        <p className="text-sm font-bold text-[color:var(--accent)]">TVS NADI</p>
        <h1 className="mt-2 text-3xl font-black">Login</h1>
        <div className="mt-6 space-y-4">
          <label>
            <span className="label">Email</span>
            <input className="field" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            <span className="label">Password</span>
            <input className="field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
        </div>
        {error ? <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        <button className="btn-primary mt-6 w-full" disabled={loading} type="submit">{loading ? "Signing in" : "Sign in"}</button>
        <p className="mt-4 text-sm text-[color:var(--muted)]">
          New borrower? <Link className="font-bold text-[color:var(--accent)]" href="/signup">Create an account</Link>
        </p>
      </form>
    </main>
  );
}
