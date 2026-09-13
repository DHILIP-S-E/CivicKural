"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import PhoneLogin from "@/components/PhoneLogin";
import { getMyReports } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { clearCitizenSession, getCitizenSession, isCitizenSessionValid, setCitizenSession } from "@/lib/citizenSession";
import CitizenAuthGuard from "@/components/CitizenAuthGuard";

const TENANT_ID = "MDU-W14";

function MyReportsContent() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [checkedSession, setCheckedSession] = useState(false);
  const [reports, setReports] = useState<any[] | null>(null);
  const [loadingReports, setLoadingReports] = useState(false);
  const [reportsError, setReportsError] = useState("");

  useEffect(() => {
    if (isCitizenSessionValid()) {
      const session = getCitizenSession();
      setLoggedIn(true);
      if (session) loadReports(session.token);
    }
    setCheckedSession(true);
  }, []);

  async function loadReports(token: string) {
    setLoadingReports(true);
    setReportsError("");
    try {
      const data = await getMyReports(TENANT_ID, token);
      setReports(data);
    } catch (cause: any) {
      setReportsError(friendlyError(cause));
    } finally {
      setLoadingReports(false);
    }
  }

  function handleVerified(token: string) {
    setCitizenSession(token);
    setLoggedIn(true);
    loadReports(token);
  }

  function logout() {
    clearCitizenSession();
    setLoggedIn(false);
    setReports(null);
    setReportsError("");
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            Phone Verification
          </div>
          <h1>My Reports</h1>
          <p>Your verified citizen session shows only reports connected to your Indian mobile number.</p>
        </div>
        <Link className="button ghost" href="/report">
          Submit a New Report
        </Link>
      </div>

      <div style={{ maxWidth: 480 }}>
        {!checkedSession ? null : !loggedIn ? (
          <PhoneLogin tenantId={TENANT_ID} onVerified={handleVerified} />
        ) : (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>Your Reports</h3>
                <p>Reports filed under your verified phone number.</p>
              </div>
              <button type="button" className="button ghost" style={{ fontSize: 13 }} onClick={logout}>
                Not you? Log out
              </button>
            </div>

            <div aria-live="polite">
              {loadingReports && (
                <div className="state-card">
                  <span className="spinner" />
                  Loading your reports…
                </div>
              )}

              {!loadingReports && reportsError && (
                <div className="alert error" role="alert">
                  {reportsError}
                </div>
              )}

              {!loadingReports && !reportsError && reports && reports.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                  </div>
                  <h3>No reports found for this number</h3>
                  <p>Reports you file will show up here once verified.</p>
                  <Link className="button" href="/report" style={{ marginTop: 16 }}>
                    Submit a New Report
                  </Link>
                </div>
              )}

              {!loadingReports && !reportsError && reports && reports.length > 0 && (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Case</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Filed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reports.map((r) => (
                        <tr key={r.complaint_id}>
                          <td>
                            <Link className="id-link" href={`/issues?id=${encodeURIComponent(r.complaint_id)}`}>
                              #{String(r.complaint_id).slice(-8)}
                            </Link>
                          </td>
                          <td style={{ textTransform: "capitalize" }}>{String(r.category).replaceAll("_", " ")}</td>
                          <td>
                            <span className={`badge ${r.status}`}>{String(r.status).replaceAll("_", " ")}</span>
                          </td>
                          <td>{new Date(r.created_at).toLocaleDateString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        )}

        <div className="privacy-note">
          <strong style={{ display: "block", marginBottom: 4 }}>Privacy-by-Design</strong>
          Your verification session is kept only in this browser and expires automatically. Log out any time to
          switch numbers.
        </div>
      </div>
    </>
  );
}

export default function MyReportsPage() {
  return <CitizenAuthGuard><MyReportsContent /></CitizenAuthGuard>;
}
