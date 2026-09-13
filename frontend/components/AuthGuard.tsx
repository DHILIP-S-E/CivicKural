"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { ensureFreshSession, getSession, isSignedIn } from "@/lib/auth";

export default function AuthGuard({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const hadSession = isSignedIn() || !!getSession();
      const session = await ensureFreshSession();
      if (cancelled) return;
      setAllowed(!!session);
      setExpired(hadSession && !session);
      setReady(true);
    })();
    return () => { cancelled = true; };
  }, []);
  if (!ready) return <div className="state-card"><span className="spinner" />Checking secure session…</div>;
  if (!allowed) return <section className="empty-state lock-state">
    <span className="empty-icon">⌾</span><h1>Officer access required</h1>
    <p>Sign in with your WardWatch account to view protected operational data.</p>
    <Link className="button" href={expired ? "/login?session_expired=1" : "/login"}>Go to secure sign in</Link>
  </section>;
  return <>{children}</>;
}
