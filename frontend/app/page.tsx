"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const WARD = "MDU-W14";

export default function Home() {
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.queue(WARD, filter || undefined).then(setRows).catch((e) => setErr(String(e)));
  }, [filter]);

  const count = (s: string) => rows.filter((r) => r.status === s).length;

  return (
    <>
      <h2>Ward {WARD} queue</h2>
      {err && <div className="card">Error: {err} — <Link href="/login">sign in</Link></div>}
      <div className="kpis">
        <div className="kpi"><b>{count("open")}</b>Open</div>
        <div className="kpi"><b>{count("in_progress")}</b>In progress</div>
        <div className="kpi"><b>{count("resolved")}</b>Resolved</div>
        <div className="kpi"><b>{rows.filter((r) => r.escalation_tier > 0).length}</b>Breached</div>
      </div>
      <div className="card">
        <label>Status filter:{" "}
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">all</option>
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="pending_verification">pending_verification</option>
            <option value="resolved">resolved</option>
          </select>
        </label>
      </div>
      <table>
        <thead><tr><th>ID</th><th>Category</th><th>Severity</th><th>Dept</th><th>SLA deadline</th><th>Tier</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.complaint_id}>
              <td><Link href={`/complaints/${WARD}/${r.complaint_id}`}>{r.complaint_id}</Link></td>
              <td>{r.category}</td>
              <td>{r.severity}</td>
              <td>{r.routed_dept}</td>
              <td>{new Date(r.sla_deadline).toLocaleDateString()}</td>
              <td className={`tier${r.escalation_tier}`}>{r.escalation_tier || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
