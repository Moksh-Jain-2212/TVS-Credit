"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProtectedRoute, StatusBadge, formatCurrency } from "@/components/platform";
import { useAuth } from "@/context/AuthContext";
import { listPlatformApplications, type PlatformApplication } from "@/lib/api";

export default function UserApplicationsPage() {
  const { accessToken } = useAuth();
  const [applications, setApplications] = useState<PlatformApplication[]>([]);

  useEffect(() => {
    if (accessToken) {
      listPlatformApplications(accessToken).then(setApplications).catch(() => setApplications([]));
    }
  }, [accessToken]);

  return (
    <ProtectedRoute role="USER">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="page-kicker">Borrower Workspace</p>
          <h1 className="page-title">Applications</h1>
        </div>
        <Link href="/user/apply" className="btn-primary">New Application</Link>
      </div>
      <div className="mt-6 grid gap-3">
        {applications.map((application) => (
          <Link className="item-card block" href={`/user/applications/${application.id}`} key={application.id}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm text-[color:var(--muted)]">Application #{application.id}</div>
                <div className="mt-1 text-lg font-bold">{formatCurrency(application.requested_amount)}</div>
                <div className="mt-1 text-xs font-bold text-[color:var(--muted)]">{application.borrower_segment?.replaceAll("_", " ") ?? "Borrower type not set"}</div>
              </div>
              <StatusBadge status={application.status} />
            </div>
          </Link>
        ))}
        {!applications.length ? <div className="empty-state">No applications yet</div> : null}
      </div>
    </ProtectedRoute>
  );
}
