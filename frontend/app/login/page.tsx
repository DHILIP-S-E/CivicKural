"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { completeNewPassword, signIn } from "@/lib/auth";

function LoginForm() {
  const searchParams = useSearchParams();
  const sessionExpired = searchParams.get("session_expired") === "1";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [challengeSession, setChallengeSession] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (challengeSession) {
        if (newPassword !== confirmPassword) throw new Error("The new passwords do not match.");
        await completeNewPassword(username, newPassword, challengeSession);
        location.href = "/";
        return;
      }
      const result = await signIn(username.trim(), password);
      if (result.status === "new_password_required") {
        setChallengeSession(result.challengeSession);
        setPassword("");
      } else {
        location.href = "/";
      }
    } catch (cause: any) {
      setError(cause.message || "Unable to sign in. Please verify your credentials.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <section className="auth-story">
        <div className="eyebrow light">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          MUNICIPAL GOVERNANCE WORKSPACE
        </div>
        <h1>Civic Kural · குடிமக்கள் குரல்</h1>
        <p>
          The authoritative command console for ward-level officers and supervisors. Track real-time case triage, vision verification, and autonomous SLA escalation.
        </p>

        <div className="trust-list">
          <span>
            <b>01</b> Ward-scoped cryptographic access control
          </span>
          <span>
            <b>02</b> Zero-PII citizen privacy guarantee
          </span>
          <span>
            <b>03</b> Continuous automated EventBridge sweeps
          </span>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="brand-mark large" aria-hidden="true">
            கு
          </div>
          <div className="eyebrow">OFFICER AUTHENTICATION</div>
          <h2>{challengeSession ? "Set New Password" : "Sign In to Ward"}</h2>
          <p>
            {challengeSession
              ? "Your account requires an updated password to activate."
              : "Enter your municipal credentials to access the operational queue."}
          </p>

          {sessionExpired && !challengeSession && (
            <div className="alert error" role="alert" style={{ marginBottom: 18 }}>
              Your session has expired. Please sign in again.
            </div>
          )}

          <form onSubmit={submit} className="form-stack">
            {!challengeSession ? (
              <>
                <label>
                  Username
                  <input
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. wardwatch-admin"
                    required
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    required
                  />
                </label>
              </>
            ) : (
              <>
                <label>
                  New Password
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Minimum 12 characters"
                    required
                  />
                </label>
                <label>
                  Confirm Password
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat new password"
                    required
                  />
                </label>
                <small style={{ color: "var(--muted)", fontSize: 12 }}>
                  Must include uppercase, lowercase, numeric digits, and special characters.
                </small>
              </>
            )}

            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}

            <button className="button full" disabled={busy} type="submit">
              {busy ? (
                <>
                  <span className="spinner" />
                  Authenticating…
                </>
              ) : challengeSession ? (
                "Save Password & Continue"
              ) : (
                "Sign In to Operations →"
              )}
            </button>
          </form>

          <div className="auth-help">
            Citizen without officer credentials?{" "}
            <Link href="/report" style={{ fontWeight: 700 }}>
              Submit a public concern
            </Link>{" "}
            or{" "}
            <Link href="/public" style={{ fontWeight: 700 }}>
              view public metrics
            </Link>
            .
          </div>
        </div>
      </section>
    </div>
  );
}

export default function Login() {
  return (
    <Suspense fallback={<div className="state-card"><span className="spinner" />Loading portal…</div>}>
      <LoginForm />
    </Suspense>
  );
}
