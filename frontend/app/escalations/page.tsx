"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const WARD = "MDU-W14";

export default function Escalations() {
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.queue(WARD).then((r) => setRows(r.filter((x: any) => x.escalation_tier > 0))).catch((e) => setErr(String(e)));
  }, []);
  return (
    <>
      <h2>Escalation log — Ward {WARD}</h2>
      {err && <div className="card">{err}</div>}
      <table>
        <thead><tr><th>ID</th><th>Category</th><th>Tier</th><th># escalations</th><th>SLA deadline</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.complaint_id}>
              <td><Link href={`/complaints/${WARD}/${r.complaint_id}`}>{r.complaint_id}</Link></td>
              <td>{r.category}</td>
              <td className={`tier${r.escalation_tier}`}>{r.escalation_tier}</td>
              <td>{r.escalation_count}</td>
              <td>{new Date(r.sla_deadline).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
