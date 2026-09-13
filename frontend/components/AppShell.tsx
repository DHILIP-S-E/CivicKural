"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { getSession, signOut, type Session } from "@/lib/auth";

const nav = [
  {
    href: "/",
    label: "Operations",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="7" height="9" x="3" y="3" rx="1" />
        <rect width="7" height="5" x="14" y="3" rx="1" />
        <rect width="7" height="9" x="14" y="12" rx="1" />
        <rect width="7" height="5" x="3" y="16" rx="1" />
      </svg>
    ),
  },
  {
    href: "/report",
    label: "Report Issue",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    ),
  },
  {
    href: "/escalations",
    label: "Escalations",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m18 15-6-6-6 6" />
      </svg>
    ),
  },
  {
    href: "/public",
    label: "Public Data",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
        <path d="M2 12h20" />
      </svg>
    ),
  },
  {
    href: "/settings",
    label: "Policy",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  {
    href: "/admin/health",
    label: "Health",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const sync = () => setSession(getSession());
    sync();
    window.addEventListener("wardwatch-auth", sync);
    return () => window.removeEventListener("wardwatch-auth", sync);
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/public" aria-label="Civic Kural home">
          <span className="brand-mark" aria-hidden="true">
            கு
          </span>
          <div>
            <b>
              Civic Kural <span className="tamil-badge">குரல்</span>
            </b>
            <small>Autonomous Ward Accountability</small>
          </div>
        </Link>

        <div className="ward-indicator" title="Active Ward Context">
          <span className="dot" />
          <span>Madurai · Ward MDU-W14</span>
        </div>

        <button
          className="menu-button"
          onClick={() => setOpen(!open)}
          aria-label="Toggle navigation"
          aria-expanded={open}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {open ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="18" x2="20" y2="18" />
              </>
            )}
          </svg>
        </button>

        <nav className={open ? "nav-open" : ""}>
          {nav.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={isActive ? "active" : ""}
                aria-current={isActive ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="account-area">
          {session ? (
            <div className="user-pill">
              <span className="avatar" aria-hidden="true">
                {session.username.slice(0, 1).toUpperCase()}
              </span>
              <span className="account-name" title={session.username}>
                {session.username}
              </span>
              <button
                className="button ghost compact"
                onClick={() => {
                  signOut();
                  location.href = "/login";
                }}
              >
                Sign out
              </button>
            </div>
          ) : (
            <Link className="button compact" href="/login">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <span>Officer Portal</span>
            </Link>
          )}
        </div>
      </header>

      <main>{children}</main>

      <footer>
        <div className="footer-left">
          <span style={{ fontWeight: 700, color: "var(--ink)" }}>Civic Kural</span>
          <span>·</span>
          <span>குடிமக்கள் குரல்</span>
          <span>·</span>
          <span>Multi-Agent Civic Integrity</span>
        </div>
        <div className="footer-right">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Zero Citizen PII Retention
          </span>
          <span>·</span>
          <span>SLA Sweep: Active (6h)</span>
        </div>
      </footer>
    </div>
  );
}
