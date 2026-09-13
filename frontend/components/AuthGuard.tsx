"use client";

import Link from "next/link";
import { ReactNode, useEffect, useState } from "react";
import { ensureFreshSession, getSession, isSignedIn, roleHome, type Session } from "@/lib/auth";

export default function AuthGuard({ children, roles }: { children: ReactNode; roles?: Session["role"][] }) {
  const [ready, setReady] = useState(false);
  const [allowed, setAllowed] = useState(false);
  const [expired, setExpired] = useState(false);
  const [actualRole, setActualRole] = useState<Session["role"] | undefined>();
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const hadSession = isSignedIn() || !!getSession();
      const session = await ensureFreshSession();
      if (cancelled) return;
      setActualRole(session?.role);
      setAllowed(!!session && (!roles || roles.includes(session.role) || (session.role === "admin" && roles.includes("officer"))));
      setExpired(hadSession && !session);
      setReady(true);
    })();
    return () => { cancelled = true; };
  }, []);
  if (!ready) return <div className="state-card"><span className="spinner" />Checking secure session…</div>;
  if (!allowed && actualRole) return <section className="empty-state lock-state">
    <span className="empty-icon">↗</span><h1>This panel belongs to another role</h1>
    <p>Your account is signed in as {actualRole}. Open the panel assigned to that role.</p>
    <Link className="button" href={roleHome(actualRole)}>Open my panel</Link>
  </section>;
  if (!allowed) return <section className="empty-state lock-state">
    <span className="empty-icon">⌾</span><h1>Officer access required</h1>
    <p>Sign in with your WardWatch account to view protected operational data.</p>
    <Link className="button" href={expired ? "/login?session_expired=1" : "/login"}>Go to secure sign in</Link>
  </section>;
  return <>{children}</>;
}
