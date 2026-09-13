"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getComplaintDetail, verifyResolution } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import CitizenAuthGuard from "@/components/CitizenAuthGuard";

function IssueDetail() {
  const id = useSearchParams().get("id") ?? "";
  const [detail, setDetail] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newPhoto, setNewPhoto] = useState<File | null>(null);
  const [photoInputKey, setPhotoInputKey] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = () => {
    if (id) {
      getComplaintDetail(id)
        .then(setDetail)
        .catch((cause) => setError(friendlyError(cause)));
    }
  };

  useEffect(() => {
    load();
  }, [id]);

  async function decide(confirmed: boolean) {
    setSubmitting(true);
    setActionError(null);
    setMessage(null);
    try {
      await verifyResolution(id, confirmed, confirmed ? null : newPhoto);
      setMessage(
        confirmed
          ? "Thank you! Your confirmation has closed this case and validated the ward's resolution record."
          : "The issue has been reopened with your feedback. Field supervisors have been alerted."
      );
      setNewPhoto(null);
      setPhotoInputKey((k) => k + 1);
      load();
    } catch (cause: any) {
      setActionError(friendlyError(cause));
    } finally {
      setSubmitting(false);
    }
  }

  if (!id) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h1>Tracking Link Missing</h1>
        <p>Please open the private tracking link generated when you submitted your report.</p>
        <Link className="button" href="/report" style={{ marginTop: 16 }}>
          Submit a New Report
        </Link>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert error" role="alert">
        <strong>Error accessing case:</strong> {error}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="state-card">
        <span className="spinner" />
        Opening encrypted citizen tracking record…
      </div>
    );
  }

  const canVerify = detail.status === "resolved" || detail.status === "pending_verification";

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Private Citizen Verification
          </div>
          <h1>Track Issue #{detail.id.slice(-8)}</h1>
          <p>
            Secure citizen tracking console. Your browser holds an unlisted encryption key to view and verify this case.
          </p>
        </div>
        <div className="toolbar">
          <span className={`badge ${detail.status}`}>
            Status: {detail.status.replaceAll("_", " ")}
          </span>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3 style={{ textTransform: "capitalize" }}>{detail.category.replaceAll("_", " ")}</h3>
              <p>
                {detail.severity} severity · {detail.priority} priority · {detail.duplicate_reports_count + 1} community voice(s)
              </p>
            </div>
            <span className="badge open">Reported: {new Date(detail.created_at).toLocaleDateString()}</span>
          </div>

          {detail.authority_ticket_id && (
            <div style={{ padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: "var(--radius-md)", border: "1px solid var(--line)", marginBottom: 16 }}>
              <span className="metric-label">Municipal Authority Dispatch</span>
              <p style={{ margin: "4px 0 0", fontWeight: 600, color: "var(--ink)" }}>
                Ticket #{detail.authority_ticket_id} · {detail.authority_status}
              </p>
            </div>
          )}

          {detail.updates && detail.updates.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", marginBottom: 8 }}>
                Operational Updates
              </h4>
              {detail.updates.map((update: string, index: number) => (
                <div className="flag" key={index} style={{ borderLeftColor: "var(--brand)" }}>
                  <p>{update}</p>
                </div>
              ))}
            </div>
          )}

          {detail.citizen_disputed && (
            <div className="alert error" style={{ marginBottom: 16 }}>
              <strong>Disputed:</strong> You previously noted that this issue was not adequately fixed.
            </div>
          )}

          <div>
            <h4 style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", marginBottom: 12 }}>
              Evidence Comparison
            </h4>
            <div className="evidence-grid">
              <div className="card" style={{ marginBottom: 0, padding: 14 }}>
                <span className="metric-label" style={{ display: "block", marginBottom: 6 }}>
                  Before (Intake Report)
                </span>
                {detail.before_photo_url ? (
                  <img src={detail.before_photo_url} alt="Before Resolution" />
                ) : (
                  <div style={{ height: 160, display: "grid", placeItems: "center", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)", color: "var(--muted)" }}>
                    No intake photo provided
                  </div>
                )}
              </div>

              <div className="card" style={{ marginBottom: 0, padding: 14 }}>
                <span className="metric-label" style={{ display: "block", marginBottom: 6 }}>
                  After (Field Completion Proof)
                </span>
                {detail.after_photo_url ? (
                  <img src={detail.after_photo_url} alt="After Resolution" />
                ) : (
                  <div style={{ height: 160, display: "grid", placeItems: "center", background: "var(--bg-subtle)", borderRadius: "var(--radius-sm)", color: "var(--muted)" }}>
                    Field evidence not yet submitted
                  </div>
                )}
              </div>
            </div>
          </div>

          <div aria-live="polite" style={{ marginTop: 16 }}>
            {message && <div className="alert success">{message}</div>}
            {actionError && <div className="alert error" role="alert">{actionError}</div>}
          </div>
        </div>

        <aside>
          {canVerify ? (
            <div className="panel" style={{ border: "2px solid var(--brand-light)" }}>
              <div className="eyebrow">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Citizen Decision Required
              </div>
              <h3 style={{ marginTop: 4 }}>Is the issue properly fixed?</h3>
              <p style={{ margin: "6px 0 16px", fontSize: 13.5 }}>
                Municipal officers marked this case complete. As the citizen who reported it, you have final authority to confirm or reject.
              </p>

              <div className="form-stack">
                <button
                  className="button full"
                  disabled={submitting}
                  onClick={() => decide(true)}
                  style={{ background: "var(--brand)" }}
                >
                  {submitting ? (
                    <>
                      <span className="spinner" />
                      Confirming…
                    </>
                  ) : (
                    "✓ Yes, Confirmed Fixed"
                  )}
                </button>

                <div style={{ borderTop: "1px solid var(--line)", paddingTop: 14 }}>
                  <p style={{ fontSize: 13, marginBottom: 8, fontWeight: 600, color: "var(--ink)" }}>
                    Not fixed? Attach evidence & reopen:
                  </p>
                  <label className="upload-zone" style={{ padding: 14, marginBottom: 12 }}>
                    <div style={{ fontSize: 13 }}>
                      {newPhoto ? <strong>{newPhoto.name}</strong> : "Attach current photo showing ongoing problem"}
                    </div>
                    <input
                      key={photoInputKey}
                      type="file"
                      accept="image/*"
                      onChange={(e) => setNewPhoto(e.target.files?.[0] ?? null)}
                    />
                  </label>

                  <button
                    className="button danger full"
                    disabled={submitting}
                    onClick={() => decide(false)}
                  >
                    {submitting ? (
                      <>
                        <span className="spinner" />
                        Submitting dispute…
                      </>
                    ) : (
                      "Still a Problem · Reopen Case"
                    )}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="panel">
              <div className="eyebrow">Current Phase</div>
              <h3>Under Autonomous Tracking</h3>
              <p style={{ margin: "6px 0 0", fontSize: 13.5 }}>
                Field teams are actively addressing this issue. Once resolution evidence is submitted, your verification options will activate here.
              </p>
            </div>
          )}

          <div className="privacy-note">
            <strong>Browser Token Secured</strong>
            <br />
            This private tracking view is cryptographically bound to your browser token. No other citizen or public dashboard visitor can see your individual submission.
          </div>
        </aside>
      </div>
    </>
  );
}

export default function IssuePage() {
  return (
    <CitizenAuthGuard>
      <Suspense fallback={<div className="state-card"><span className="spinner" />Loading citizen tracking…</div>}>
        <IssueDetail />
      </Suspense>
    </CitizenAuthGuard>
  );
}
