"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!user) {
      router.replace("/login");
      return;
    }
    router.replace(user.role === "ADMIN" ? "/admin/dashboard" : "/user/dashboard");
  }, [loading, router, user]);

  return <div className="page-center">Loading TVS NADI</div>;
}
