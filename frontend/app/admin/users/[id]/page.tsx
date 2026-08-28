"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApplicationSummary, ProtectedRoute } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { getAdminUser, type AuthUser, type PlatformApplication } from "@/lib/api";

export default function AdminUserPage() {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const [detail, setDetail] = useState<{ user: AuthUser & { created_at: string }; applications: PlatformApplication[] } | null>(null);

  useEffect(() => {
    if (accessToken && id) {
      getAdminUser(Number(id), accessToken).then(setDetail).catch(() => setDetail(null));
    }
  }, [accessToken, id]);

  return (
    <ProtectedRoute role="ADMIN">
      {detail ? (
        <div className="grid gap-6">
          <section className="section-panel">
            <p className="text-sm font-bold text-[color:var(--accent)]">User #{id}</p>
            <h1 className="mt-2 text-3xl font-black">{detail.user.name}</h1>
            <div className="mt-4 grid gap-2 text-sm text-[color:var(--muted)]">
              <div>{detail.user.email}</div>
              <div>{detail.user.phone ?? "No phone"}</div>
              <div>{detail.user.role}</div>
            </div>
          </section>
          {detail.applications.map((application) => <ApplicationSummary application={application} key={application.id} />)}
        </div>
      ) : <div className="empty-state">Loading borrower profile</div>}
    </ProtectedRoute>
  );
}
