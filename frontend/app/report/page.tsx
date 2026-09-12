"use client";
import { useState } from "react";
import { getNearbyComplaints, submitReport, supportComplaint } from "@/lib/api";

const WARDS = ["MDU-W14"];
const CATEGORIES = [
  { value: "", label: "Not sure / let AI decide" },
  { value: "pothole", label: "Pothole" },
  { value: "garbage", label: "Garbage" },
  { value: "water_leak", label: "Water leak" },
  { value: "streetlight", label: "Streetlight" },
  { value: "other", label: "Other" },
];

export default function ReportPage() {
  const [transcript, setTranscript] = useState("");
  const [wardId, setWardId] = useState(WARDS[0]);
  const [category, setCategory] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [video, setVideo] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [locating, setLocating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [nearby, setNearby] = useState<any[] | null>(null);
  const [supported, setSupported] = useState<Record<string, boolean>>({});

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setLocating(false);
        loadNearby(pos.coords.latitude, pos.coords.longitude);
      },
      (err) => {
        setError(`Could not get location: ${err.message}`);
        setLocating(false);
      }
    );
  }

  async function loadNearby(la: number, ln: number) {
    try {
      const data = await getNearbyComplaints({ lat: la, lng: ln, category: category || undefined });
      setNearby(data.complaints);
    } catch {
      /* nearby lookup is a nice-to-have, ignore failures */
    }
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Voice recording is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: BlobPart[] = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        setAudio(new File([blob], "voice-note.webm", { type: "audio/webm" }));
        stream.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      setRecorder(rec);
      setRecording(true);
    } catch (e: any) {
      setError(`Could not start recording: ${e.message}`);
    }
  }

  function stopRecording() {
    recorder?.stop();
    setRecording(false);
    setRecorder(null);
  }

  async function handleSupport(id: string) {
    try {
      await supportComplaint(id, wardId);
      setSupported((s) => ({ ...s, [id]: true }));
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);
    try {
      const res = await submitReport({
        transcript,
        wardId,
        lat: lat ?? undefined,
        lng: lng ?? undefined,
        photo,
        audio,
        video,
      });
      setResult(res);
      if (lat !== null && lng !== null) loadNearby(lat, lng);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h2>Report a civic issue</h2>
      <p>Describe the problem, add a photo if you have one, and share the location.</p>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div>
            <label htmlFor="transcript">Description</label>
            <br />
            <textarea
              id="transcript"
              rows={4}
              style={{ width: "100%" }}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="e.g. There is a large pothole near the bus stand blocking traffic"
              required
            />
          </div>

          <div>
            <label htmlFor="photo">Photo (optional)</label>
            <br />
            <input
              id="photo"
              type="file"
              accept="image/*"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            />
          </div>

          <div>
            <label>Voice note (optional)</label>
            <br />
            {!recording ? (
              <button type="button" onClick={startRecording}>
                🎙 Record voice note
              </button>
            ) : (
              <button type="button" onClick={stopRecording}>
                ⏹ Stop recording
              </button>
            )}{" "}
            {audio && <span>Voice note recorded ({audio.name})</span>}
          </div>

          <div>
            <label htmlFor="video">Video (optional)</label>
            <br />
            <input
              id="video"
              type="file"
              accept="video/*"
              onChange={(e) => setVideo(e.target.files?.[0] ?? null)}
            />
          </div>

          <div>
            <label htmlFor="ward">Ward</label>
            <br />
            <select id="ward" value={wardId} onChange={(e) => setWardId(e.target.value)}>
              {WARDS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="category">Category (optional, helps find similar reports)</label>
            <br />
            <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <button type="button" onClick={useMyLocation} disabled={locating}>
              {locating ? "Locating…" : "Use my location"}
            </button>{" "}
            {lat !== null && lng !== null && (
              <span>
                Location set: {lat.toFixed(5)}, {lng.toFixed(5)}
              </span>
            )}
          </div>

          <div style={{ marginTop: "1rem" }}>
            <button type="submit" disabled={submitting || !transcript}>
              {submitting ? "Submitting…" : "Submit report"}
            </button>
          </div>
        </form>

        {error && (
          <p role="alert" style={{ color: "crimson" }}>
            {error}
          </p>
        )}

        {result && result.status === "created" && (
          <div className="card" style={{ borderColor: "green" }}>
            <b>Thanks — your report is logged.</b>
            <p>
              Complaint ID: <code>{result.complaint_id}</code>
            </p>
            <p>{result.message}</p>
          </div>
        )}

        {result && result.status === "needs_more_info" && (
          <div className="card" style={{ borderColor: "orange" }}>
            <b>We need a bit more information</b>
            <p>{result.message}</p>
          </div>
        )}
      </div>

      {nearby && nearby.length > 0 && (
        <div className="card">
          <b>Similar reports nearby</b>
          <p>If one of these matches your issue, support it instead of filing a duplicate.</p>
          <ul>
            {nearby.map((c) => (
              <li key={c.id} style={{ marginBottom: "0.5rem" }}>
                #{c.id} — {c.category} ({c.severity}) — {c.status} — {c.duplicate_reports_count}{" "}
                report(s) so far
                <br />
                <button
                  type="button"
                  disabled={!!supported[c.id]}
                  onClick={() => handleSupport(c.id)}
                >
                  {supported[c.id] ? "Supported ✓" : "This is happening to me too — Support this report"}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
