"use client";

import { FormEvent, useState, useEffect } from "react";
import Link from "next/link";
import { getNearbyComplaints, setCitizenToken, submitReport, supportComplaint } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import PhoneLogin from "@/components/PhoneLogin";
import { clearCitizenSession, getCitizenSession, isCitizenSessionValid, setCitizenSession } from "@/lib/citizenSession";
import CitizenAuthGuard from "@/components/CitizenAuthGuard";

const TENANT_ID = "MDU-W14";
const MIN_DESCRIPTION_LENGTH = 10;

const CATEGORIES = [
  ["", "✦ Let AI identify the issue automatically"],
  ["pothole", "🚧 Pothole / Damaged Road Surface"],
  ["garbage", "🗑 Waste / Garbage Overflow"],
  ["water_leak", "💧 Pipeline Leak / Water Stagnation"],
  ["streetlight", "💡 Broken Streetlight / Darkness"],
  ["other", "⚙ Other Civic Infrastructure Issue"],
];

function ReportContent() {
  const [checkedSession, setCheckedSession] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [category, setCategory] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [video, setVideo] = useState<File | null>(null);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [locating, setLocating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [nearby, setNearby] = useState<any[]>([]);
  const [supported, setSupported] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoggedIn(isCitizenSessionValid());
    setCheckedSession(true);
  }, []);

  function handleVerified(token: string) {
    setCitizenSession(token);
    setLoggedIn(true);
  }

  function logout() {
    clearCitizenSession();
    setLoggedIn(false);
  }

  useEffect(() => {
    let interval: any = null;
    if (recording) {
      interval = setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    } else {
      setRecordSeconds(0);
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [recording]);

  async function findNearby(la: number, ln: number) {
    try {
      const data = await getNearbyComplaints({ lat: la, lng: ln, category: category || undefined });
      setNearby(data.community_issues);
    } catch {}
  }

  function locate() {
    setError("");
    if (!navigator.geolocation) return setError("Geolocation is not supported by your browser.");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLat(p.coords.latitude);
        setLng(p.coords.longitude);
        setLocating(false);
        findNearby(p.coords.latitude, p.coords.longitude);
      },
      (e) => {
        setError(`Location unavailable: ${e.message}`);
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function startVoice() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: BlobPart[] = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        setAudio(new File([new Blob(chunks, { type: "audio/webm" })], "voice-note.webm", { type: "audio/webm" }));
        stream.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      setRecorder(rec);
      setRecording(true);
    } catch (e: any) {
      setError(`Microphone access failed: ${e.message}`);
    }
  }

  function stopVoice() {
    recorder?.stop();
    setRecorder(null);
    setRecording(false);
  }

  async function support(ref: string) {
    try {
      await supportComplaint(ref);
      setSupported((s) => ({ ...s, [ref]: true }));
    } catch (e: any) {
      setError(friendlyError(e));
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setResult(null);

    if (transcript.trim().length < MIN_DESCRIPTION_LENGTH) {
      setError(`Please describe the issue in a bit more detail (minimum ${MIN_DESCRIPTION_LENGTH} characters).`);
      return;
    }

    const citizenSession = getCitizenSession();
    if (!citizenSession) {
      setError("Your verification session has expired. Please log in again.");
      setLoggedIn(false);
      return;
    }

    setSubmitting(true);
    try {
      const res = await submitReport({
        transcript,
        wardId: "MDU-W14",
        lat: lat ?? undefined,
        lng: lng ?? undefined,
        photo,
        audio,
        video,
        phoneSessionToken: citizenSession.token,
      });
      setResult(res);
      if (res.complaint_id && res.citizen_access_token) {
        setCitizenToken(res.complaint_id, res.citizen_access_token);
      }
      if (lat !== null && lng !== null) {
        findNearby(lat, lng);
      }
    } catch (e: any) {
      setError(friendlyError(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            Citizen Intake Portal
          </div>
          <h1>Submit a Civic Concern</h1>
          <p>
            Your report is autonomously analyzed, deduplicated, mapped, and assigned a legally enforceable SLA. Speak or type in your language.
          </p>
        </div>
        <div className="toolbar">
          <Link className="button ghost" href="/my-reports">
            View My Reports
          </Link>
          <Link className="button ghost" href="/public">
            View Public Dashboard
          </Link>
          {loggedIn && (
            <button type="button" className="button ghost" onClick={logout}>
              Not you? Log out
            </button>
          )}
        </div>
      </div>

      {!checkedSession ? null : !loggedIn ? (
        <div style={{ maxWidth: 480 }}>
          <PhoneLogin
            tenantId={TENANT_ID}
            onVerified={handleVerified}
            title="Verify Your Phone Number"
            description="We'll send a WhatsApp one-time code to verify you before you can submit a report."
          />
        </div>
      ) : (
        <>

      <div className="report-layout">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>Report Details</h3>
              <p>Share photos, voice recordings, and text descriptions.</p>
            </div>
            <span className="badge open">Ward MDU-W14 · Madurai</span>
          </div>

          <form className="form-stack" onSubmit={submit}>
            <div>
              <label htmlFor="transcript">
                What needs attention?
                <textarea
                  id="transcript"
                  rows={4}
                  maxLength={1000}
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                  placeholder="Example: Deep waterlogged pothole on North Veli Street right next to the bus shelter, vehicles are swerving dangerously…"
                  required
                />
              </label>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 12, color: "var(--muted)" }}>
                <span>Minimum {MIN_DESCRIPTION_LENGTH} characters for AI routing</span>
                <span style={{ fontWeight: transcript.length >= 10 ? 600 : 400, color: transcript.length >= 10 ? "var(--brand)" : "inherit" }}>
                  {transcript.length} / 1000
                </span>
              </div>
            </div>

            <div className="form-grid">
              <label>
                Category
                <select value={category} onChange={(e) => setCategory(e.target.value)}>
                  {CATEGORIES.map(([value, text]) => (
                    <option key={value} value={value}>
                      {text}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Administrative Ward
                <input value="Ward MDU-W14 · Madurai Central" disabled style={{ background: "var(--bg-subtle)", color: "var(--muted)" }} />
              </label>

              <label className="upload-zone">
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
                    <circle cx="12" cy="13" r="3" />
                  </svg>
                  <span>{photo ? photo.name : "Attach Photo Evidence"}</span>
                  <small style={{ color: "var(--muted)" }}>JPG, PNG or WEBP</small>
                </div>
                <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </label>

              <label className="upload-zone">
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m22 8-6 4 6 4V8Z" />
                    <rect width="14" height="12" x="2" y="6" rx="2" ry="2" />
                  </svg>
                  <span>{video ? video.name : "Attach Video Clip"}</span>
                  <small style={{ color: "var(--muted)" }}>MP4 or WebM (under 30s)</small>
                </div>
                <input type="file" accept="video/*" onChange={(e) => setVideo(e.target.files?.[0] ?? null)} />
              </label>
            </div>

            <div className="toolbar" style={{ background: "var(--bg-subtle)", padding: "12px 16px", borderRadius: "var(--radius-md)", border: "1px solid var(--line)" }}>
              <button
                type="button"
                className={`button ${recording ? "danger" : "secondary"}`}
                onClick={recording ? stopVoice : startVoice}
              >
                {recording ? (
                  <>
                    <span className="recording-pulse" />
                    Stop Voice Note ({recordSeconds}s)
                  </>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" x2="12" y1="19" y2="22" />
                    </svg>
                    Record Voice Note
                  </>
                )}
              </button>

              <button type="button" className="button secondary" onClick={locate} disabled={locating}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" x2="12" y1="2" y2="5" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                  <line x1="2" x2="5" y1="12" y2="12" />
                  <line x1="19" x2="22" y1="12" y2="12" />
                  <circle cx="12" cy="12" r="7" />
                </svg>
                {locating ? "Pinning GPS…" : "Pin Current GPS Location"}
              </button>

              {audio && (
                <span className="badge resolved">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Voice Memo Attached
                </span>
              )}

              {lat !== null && lng !== null && (
                <span className="badge resolved" title={`GPS: ${lat.toFixed(5)}, ${lng.toFixed(5)}`}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                    <circle cx="12" cy="10" r="3" />
                  </svg>
                  GPS: {lat.toFixed(4)}, {lng.toFixed(4)}
                </span>
              )}
            </div>

            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}

            <button className="button full" disabled={submitting} type="submit">
              {submitting ? (
                <>
                  <span className="spinner" />
                  IntakeAgent analyzing & routing…
                </>
              ) : (
                <>
                  Submit Secure Report
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" x2="19" y1="12" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </>
              )}
            </button>
          </form>

          <div aria-live="polite">
            {result?.status === "created" && (
              <div className="alert success" style={{ marginTop: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 16, fontWeight: 700 }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6 9 17 4 12" />
                  </svg>
                  Report Received & Encrypted
                </div>
                <p style={{ margin: "6px 0 14px", color: "var(--brand-dark)" }}>{result.message}</p>
                <Link className="button" href={`/issues?id=${encodeURIComponent(result.complaint_id)}`}>
                  Track Case #{result.complaint_id.slice(-8)} →
                </Link>
              </div>
            )}

            {result?.status === "needs_more_info" && (
              <div className="alert" style={{ marginTop: 20 }}>
                <strong>More Details Needed</strong>
                <p>{result.message}</p>
              </div>
            )}
          </div>
        </section>

        <aside>
          <div className="panel">
            <div className="eyebrow">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" x2="12" y1="16" y2="12" />
                <line x1="12" x2="12.01" y1="8" y2="8" />
              </svg>
              Multi-Agent Pipeline
            </div>
            <div className="step-list">
              <div className="step-item">
                <span className="step-number">1</span>
                <div>
                  <b>Intake & Deduplication</b>
                  <p>Vision + Voice + GPS models parse your report, checking for nearby duplicate issues.</p>
                </div>
              </div>
              <div className="step-item">
                <span className="step-number">2</span>
                <div>
                  <b>SLA & Automated Routing</b>
                  <p>Assigned to the correct ward department with an SLA countdown timer.</p>
                </div>
              </div>
              <div className="step-item">
                <span className="step-number">3</span>
                <div>
                  <b>Citizen Verification</b>
                  <p>Once field officers upload proof, you confirm if it was truly resolved.</p>
                </div>
              </div>
            </div>
          </div>

          <div className="privacy-note">
            <strong style={{ display: "block", marginBottom: 4 }}>Privacy-by-Design</strong>
            Your personal identity is tokenized inside your browser. No public user can view your phone number, exact GPS coordinate, or raw photo.
          </div>
        </aside>
      </div>

      {nearby.length > 0 && (
        <section className="panel" style={{ marginTop: 24 }}>
          <div className="panel-head">
            <div>
              <h3>Similar Issues Reported Nearby</h3>
              <p>Strengthen community weight by confirming existing issues in your vicinity.</p>
            </div>
          </div>
          <div className="form-grid">
            {nearby.map((item) => (
              <div className="card" key={item.community_ref} style={{ marginBottom: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className={`badge ${item.priority}`}>{item.priority} Priority</span>
                  <span className="badge">{item.report_count} Reports</span>
                </div>
                <h3 style={{ textTransform: "capitalize", marginTop: 12 }}>
                  {item.category.replaceAll("_", " ")}
                </h3>
                <p style={{ fontSize: 13, margin: "6px 0 16px" }}>
                  Status: <strong>{item.status.replaceAll("_", " ")}</strong>
                </p>
                <button
                  type="button"
                  className={supported[item.community_ref] ? "button secondary" : "button"}
                  aria-label={`This affects me too — support report ${item.community_ref}`}
                  disabled={supported[item.community_ref]}
                  onClick={() => support(item.community_ref)}
                  style={{ width: "100%" }}
                >
                  {supported[item.community_ref] ? (
                    <>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      Voice Added · Supported
                    </>
                  ) : (
                    "This Affects Me Too (+1)"
                  )}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
        </>
      )}
    </>
  );
}

export default function ReportPage() {
  return <CitizenAuthGuard><ReportContent /></CitizenAuthGuard>;
}
