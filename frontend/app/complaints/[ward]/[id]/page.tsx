"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function Detail() {
  const { ward, id } = useParams<{ ward: string; id: string }>();
  const [c, setC] = useState<any>(null);
  const [msg, setMsg] = useState("");

  const load = () => api.detail(ward, id).then(setC).catch((e) => setMsg(String(e)));
  useEffect(() => { load(); }, [ward, id]);

  if (!c) return <div className="card">{msg || "Loading…"}</div>;

  const onVerify = async (e: any) => {
    const file: File = e.target.files[0];
    if (!file) return;
    const b64 = btoa(String.fromCharCode(...new Uint8Array(await file.arrayBuffer())));
    const res = await api.verify(ward, id, b64);
    setMsg(`Verification: ${res.outcome.status} — ${res.outcome.reason}`);
    load();
  };

  return (
    <>
      <h2>{c.complaint_id}</h2>
      <div className="card">
        <p><b>Status:</b> {c.status} &nbsp; <b>Category:</b> {c.category} &nbsp; <b>Severity:</b> {c.severity}</p>
        <p><b>Dept:</b> {c.routed_dept} &nbsp; <b>Escalation tier:</b> {c.escalation_tier} (x{c.escalation_count})</p>
        <p><b>Reporter:</b> {c.citizen_phone_hash}</p>
        <p><b>Description:</b> {c.description}</p>
        <p><b>Location:</b> {c.geo.lat.toFixed(5)}, {c.geo.lng.toFixed(5)} ({c.geo.source})</p>
        {c.needs_dedup_review && <p className="tier1">⚠ Flagged for dedup review (text-only location match)</p>}
        {c.photo_url && <img src={c.photo_url} alt="before" style={{ maxWidth: "100%", borderRadius: 8 }} />}
      </div>

      <div className="card">
        <b>Status timeline</b>
        <ul>
          {c.status_history.map((s: any, i: number) => (
            <li key={i}>{new Date(s.ts).toLocaleString()} — {s.status}{s.note ? ` (${s.note})` : ""}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <button onClick={() => api.setStatus(ward, id, "in_progress").then(load)}>Mark in progress</button>
        {" "}
        <label>Upload "after" photo to resolve: <input type="file" accept="image/*" onChange={onVerify} /></label>
        {msg && <p>{msg}</p>}
      </div>
    </>
  );
}
