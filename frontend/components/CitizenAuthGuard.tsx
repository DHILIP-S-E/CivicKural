"use client";

import { ReactNode, useEffect, useState } from "react";
import { isCitizenSessionValid } from "@/lib/citizenSession";

export default function CitizenAuthGuard({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!isCitizenSessionValid()) {
      const next = `${location.pathname}${location.search}`;
      location.replace(`/login?mode=citizen&next=${encodeURIComponent(next)}`);
      return;
    }
    setReady(true);
  }, []);
  if (!ready) return <div className="state-card"><span className="spinner" />Checking citizen session…</div>;
  return <>{children}</>;
}
