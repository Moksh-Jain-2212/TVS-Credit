"use client";

import Link from "next/link";
import Lightfall from "@/components/Lightfall";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

export default function Home() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const dashboard = user?.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard";
  return (
    <main className={`hero-shell relative overflow-hidden ${theme === "light" ? "hero-light" : "hero-dark"}`}>
      <Lightfall lightMode={theme === "light"} />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-7xl flex-col justify-between px-5 py-6">
        <nav className="flex items-center justify-between">
          <div className="text-xl font-black">TVS NADI</div>
          <div className="flex gap-2">
            <Link className="btn-secondary text-[color:var(--foreground)]" href="/login">Login</Link>
            <Link className="btn-primary" href={user ? dashboard : "/signup"}>{user ? "Dashboard" : "Start"}</Link>
          </div>
        </nav>
        <section className="max-w-3xl pb-10 pt-20 sm:pt-28">
          <div className="badge hero-badge">Adaptive Credit Path Engine</div>
          <h1 className="mt-6 text-4xl font-black leading-tight sm:text-5xl lg:text-6xl">TVS NADI</h1>
          <p className="hero-lead mt-5 max-w-2xl text-xl font-semibold leading-8">
            Credit decisions that understand evidence, capacity, and uncertainty.
          </p>
          <p className="hero-copy mt-4 max-w-2xl text-base leading-7">
            NADI separates repayment risk, financial capacity, and evidence confidence so missing credit history becomes uncertainty to resolve, not a reason to punish borrowers.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="btn-primary" href={user ? dashboard : "/signup"}>Create borrower account</Link>
            <Link className="btn-secondary text-[color:var(--foreground)]" href="/login">Loan officer login</Link>
          </div>
        </section>
        <section className="grid gap-3 pb-4 md:grid-cols-4">
          {["Privacy-conscious alternative data", "Safe-to-learn starter credit", "Transparent NADI recommendations", "Human loan-officer governance"].map((item) => (
            <div className="hero-stat text-sm font-semibold" key={item}>{item}</div>
          ))}
        </section>
      </div>
    </main>
  );
}
