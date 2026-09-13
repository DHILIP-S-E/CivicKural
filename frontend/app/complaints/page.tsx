"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, fileToBase64 } from "@/lib/api";
import AuthGuard from "@/components/AuthGuard";
import { friendlyError } from "@/lib/errors";

function ComplaintDetail() {
  const params = useSearchParams();
  const ward = params.get("ward") ?? "";
  const id = params.get("id") ?? "";
  const [complaint, setComplaint] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"success" | "error">("success");
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const load = () => {
    if (!ward || !id) return setMessage("Missing administrative ward or complaint ID.");
    api.detail(ward, id)
      .then(setComplaint)
      .catch((error) => {
        setMessage(friendlyError(error));
        setMessageKind("error");
      });
  };

  useEffect(() => {
    load();
  }, [ward, id]);

  if (!complaint) {
    return (
      <div className="state-card">
        {message ? (
          <div className="alert error">{message}</div>
        ) : (
          <>
            <span className="spinner" />
            Decrypting protected case record…
          </>
        )}
      </div>
    );
  }

  async function runAction(action: string, task: () => Promise<any>, successText: string) {
    setBusyAction(action);
    setMessage("");
    try {
      await task();
      setMessage(successText);
      setMessageKind("success");
      load();
    } catch (error) {
      setMessage(friendlyError(error));
      setMessageKind("error");
    } finally {
      setBusyAction(null);
    }
  }

  function markInProgress() {
    return runAction("in_progress", () => api.setStatus(ward, id, "in_progress"), "Case marked as In Progress. Field dispatch recorded.");
  }

  function approveAuthority() {
    return runAction("authority", () => api.submitAuthority(ward, id), "Authority ticket submission approved and synchronized.");
  }

  async function verifyAfterPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusyAction("verify");
    setMessage("");
    try {
      const result = await api.verify(ward, id, await fileToBase64(file));
      setMessage(`Verification Agent: ${result.outcome.status} — ${result.outcome.reason}`);
      setMessageKind("success");
      load();
    } catch (error) {
      setMessage(friendlyError(error));
      setMessageKind("error");
    } finally {
      setBusyAction(null);
      event.target.value = "";
    }
  }

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600, color: "var(--muted)" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to Live Queue
        </Link>
      </div>

      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M9 3v18" />
              <path d="m14 9 3 3-3 3" />
            </svg>
            Protected Case Record · Ward {ward}
          </div>
          <h1>Case #{complaint.complaint_id.slice(-8)}</h1>
          <p>Complete multi-agent audit trail, vision evidence, authority integration, and SLA lifecycle.</p>
        </div>
        <div className="toolbar">
          <span className={`badge ${complaint.priority}`}>{complaint.priority} Priority</span>
          <span className={`badge ${complaint.status}`}>{complaint.status.replaceAll("_", " ")}</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <div>
          <div className="panel">
            <div className="panel-head">
              <div>
                <h3>Issue Profile</h3>
                <p>
                  <strong style={{ textTransform: "capitalize", color: "var(--ink)" }}>{complaint.category.replaceAll("_", " ")}</strong> · {complaint.severity} Severity
                </p>
              </div>
              <span className="badge open">Score: {complaint.priority_factors?.score ?? "—"}</span>
            </div>

            <p style={{ fontSize: 16, color: "var(--ink)", lineHeight: 1.6, marginBottom: 20, background: "var(--bg-subtle)", padding: 16, borderRadius: "var(--radius-md)", border: "1px solid var(--line)" }}>
              {complaint.description}
            </p>

            <div className="form-grid" style={{ marginBottom: 20 }}>
              <div>
                <small className="metric-label">Responsible Department</small>
                <b style={{ display: "block", fontSize: 16, marginTop: 4 }}>{complaint.routed_dept}</b>
              </div>
              <div>
                <small className="metric-label">Authority Ticket</small>
                <b style={{ display: "block", fontSize: 16, marginTop: 4 }}>
                  {complaint.authority_ticket_id ? `${complaint.authority_ticket_id} (${complaint.authority_status})` : "Unassigned"}
                </b>
              </div>
              <div>
                <small className="metric-label">Escalation Status</small>
                <b style={{ display: "block", fontSize: 16, marginTop: 4, color: complaint.escalation_tier > 0 ? "var(--red)" : "inherit" }}>
                  Tier {complaint.escalation_tier} · {complaint.escalation_count} Notice(s)
                </b>
              </div>
              <div>
                <small className="metric-label">GPS Geolocation</small>
                <b style={{ display: "block", fontSize: 14, marginTop: 4 }}>
                  {complaint.geo?.lat?.toFixed(5)}, {complaint.geo?.lng?.toFixed(5)} ({complaint.geo?.source})
                </b>
              </div>
            </div>

            {complaint.needs_dedup_review && (
              <div className="alert" style={{ marginBottom: 18, background: "var(--amber-soft)", color: "var(--amber-dark)", borderColor: "rgba(245, 158, 11, 0.3)" }}>
                <strong>⚠ Deduplication Review Required:</strong> Nearby complaint identified within confidence radius.
              </div>
            )}

            {complaint.photo_url && (
              <div style={{ marginTop: 16 }}>
                <b style={{ display: "block", marginBottom: 8, fontSize: 14 }}>Citizen Intake Photo</b>
                <div style={{ maxWidth: 420, borderRadius: "var(--radius-md)", overflow: "hidden", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}>
                  <img src={complaint.photo_url} alt="Citizen Evidence" style={{ width: "100%", display: "block" }} />
                </div>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h3>Immutable Operational Timeline</h3>
                <p>Verifiable event ledger managed by system agents</p>
              </div>
            </div>
            <ul className="timeline">
              {complaint.status_history?.map((event: any, index: number) => (
                <li key={index}>
                  <b style={{ textTransform: "capitalize", color: "var(--ink)" }}>{event.status.replaceAll("_", " ")}</b>
                  <br />
                  <small style={{ color: "var(--muted)", fontSize: 12 }}>
                    {new Date(event.ts).toLocaleString()}
                    {event.note ? ` · ${event.note}` : ""}
                  </small>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <aside>
          <div className="panel">
            <div className="panel-head">
              <div>
                <h3>Officer Actions</h3>
                <p>Authenticated operator controls</p>
              </div>
            </div>
            <div className="form-stack">
              <button
                className="button full"
                onClick={markInProgress}
                disabled={busyAction !== null || complaint.status === "in_progress"}
              >
                {busyAction === "in_progress" ? (
                  <>
                    <span className="spinner" />
                    Updating…
                  </>
                ) : (
                  "Mark Case In Progress"
                )}
              </button>

              {!complaint.authority_ticket_id && (
                <button
                  className="button secondary full"
                  onClick={approveAuthority}
                  disabled={busyAction !== null}
                >
                  {busyAction === "authority" ? (
                    <>
                      <span className="spinner" />
                      Dispatching to Authority…
                    </>
                  ) : (
                    "Approve Authority Submission"
                  )}
                </button>
              )}

              <div>
                <label className="upload-zone" style={{ display: "block" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="16 16 12 12 8 16" />
                      <line x1="12" x2="12" y1="12" y2="21" />
                      <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
                    </svg>
                    <span>Upload After-Work Evidence</span>
                    <small style={{ color: "var(--muted)" }}>VerificationAgent will inspect fix</small>
                  </div>
                  <input type="file" accept="image/*" onChange={verifyAfterPhoto} disabled={busyAction !== null} />
                  {busyAction === "verify" && (
                    <p style={{ marginTop: 10, color: "var(--brand)", fontWeight: 600 }}>
                      <span className="spinner" />
                      Bedrock Claude comparing before/after…
                    </p>
                  )}
                </label>
              </div>

              <div aria-live="polite">
                {message && (
                  <div className={`alert ${messageKind === "error" ? "error" : "success"}`} role={messageKind === "error" ? "alert" : "status"}>
                    {message}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="privacy-note">
            <strong>Access Control: Ward Officer Role</strong>
            <br />
            This record contains operational details scoped strictly to authorized municipal officers for Ward {ward}.
          </div>
        </aside>
      </div>
    </>
  );
}

export default function ComplaintPage() {
  return (
    <AuthGuard>
      <Suspense fallback={<div className="state-card"><span className="spinner" />Loading protected case record…</div>}>
        <ComplaintDetail />
      </Suspense>
    </AuthGuard>
  );
}
