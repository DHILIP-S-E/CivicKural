"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getComplaintDetail, verifyResolution } from "@/lib/api";

export default function IssueDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [detail, setDetail] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRejectPhoto, setShowRejectPhoto] = useState(false);
  const [newPhoto, setNewPhoto] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function load() {
    getComplaintDetail(id)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      await verifyResolution(id, true);
      setMessage("Thanks for confirming the resolution.");
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject() {
    setSubmitting(true);
    setError(null);
    try {
      await verifyResolution(id, false, newPhoto);
      setMessage("Reported as not resolved — the issue has been reopened.");
      setShowRejectPhoto(false);
      setNewPhoto(null);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (error) return <p role="alert" style={{ color: "crimson" }}>{error}</p>;
  if (!detail) return <p>Loading…</p>;

  const canVerify = detail.status === "resolved" || detail.status === "pending_verification";

  return (
    <>
      <h2>Issue #{detail.id}</h2>
      <div className="card">
        <p>
          Category: <b>{detail.category}</b> &middot; Severity: <b>{detail.severity}</b> &middot;
          Status: <b>{detail.status}</b>
        </p>
        <p>Reported: {new Date(detail.created_at).toLocaleString()}</p>
        <p>{detail.duplicate_reports_count} report(s) of this issue.</p>
        {detail.citizen_disputed && <p style={{ color: "crimson" }}>You disputed this resolution.</p>}

        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <b>Before</b>
            <br />
            {detail.before_photo_url ? (
              <img src={detail.before_photo_url} alt="before" style={{ maxWidth: 280 }} />
            ) : (
              <p>No before photo.</p>
            )}
          </div>
          <div>
            <b>After</b>
            <br />
            {detail.after_photo_url ? (
              <img src={detail.after_photo_url} alt="after" style={{ maxWidth: 280 }} />
            ) : (
              <p>No after photo yet.</p>
            )}
          </div>
        </div>

        {canVerify && (
          <div style={{ marginTop: "1rem" }}>
            <b>Is this issue actually resolved?</b>
            <br />
            <button type="button" disabled={submitting} onClick={handleConfirm}>
              Confirm — it's fixed
            </button>{" "}
            <button type="button" disabled={submitting} onClick={() => setShowRejectPhoto(true)}>
              Reject — still a problem
            </button>

            {showRejectPhoto && (
              <div style={{ marginTop: "0.5rem" }}>
                <label htmlFor="dispute-photo">Optional photo showing the issue still exists</label>
                <br />
                <input
                  id="dispute-photo"
                  type="file"
                  accept="image/*"
                  onChange={(e) => setNewPhoto(e.target.files?.[0] ?? null)}
                />
                <br />
                <button type="button" disabled={submitting} onClick={handleReject}>
                  {submitting ? "Submitting…" : "Submit rejection"}
                </button>
              </div>
            )}
          </div>
        )}

        {message && (
          <div className="card" style={{ borderColor: "green", marginTop: "1rem" }}>
            {message}
          </div>
        )}
      </div>
    </>
  );
}
