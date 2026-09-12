"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Leaflet touches `window` at import time, so it must never be pulled into the
// server bundle — load it client-side only.
const HotspotMap = dynamic(() => import("./HotspotMap"), { ssr: false });

export default function PublicPage() {
  const [c, setC] = useState<any>(null);
  const [h, setH] = useState<any>(null);
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    api.compliance().then(setC).catch(() => {});
    api.hotspots().then(setH).catch(() => {});
    api.dashboard().then(setD).catch(() => {});
  }, []);

  return (
    <>
      <h2>Public accountability</h2>
      <p>Department-level only. No individual complaint, photo, address or name is shown here.</p>
      <div className="card">
        <b>Ward dashboard</b>
        {d && (
          <>
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", margin: "0.75rem 0" }}>
              <div className="card" style={{ minWidth: 120 }}>
                <div>Total</div>
                <b style={{ fontSize: "1.5rem" }}>{d.total}</b>
              </div>
              <div className="card" style={{ minWidth: 120 }}>
                <div>Open</div>
                <b style={{ fontSize: "1.5rem" }}>{d.status_totals.open ?? 0}</b>
              </div>
              <div className="card" style={{ minWidth: 120 }}>
                <div>Resolved</div>
                <b style={{ fontSize: "1.5rem" }}>{d.status_totals.resolved ?? 0}</b>
              </div>
              <div className="card" style={{ minWidth: 120 }}>
                <div>Resolution rate</div>
                <b style={{ fontSize: "1.5rem" }}>{Math.round(d.resolution_rate * 100)}%</b>
              </div>
            </div>
            <b>Top categories</b>
            <ol>
              {d.top_categories.map((tc: any) => (
                <li key={tc.category}>
                  {tc.category} — {tc.count}
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
      <div className="card">
        <b>Department SLA compliance</b>
        <table>
          <thead><tr><th>Department</th><th>Resolved within SLA</th><th>Resolved count</th></tr></thead>
          <tbody>
            {c && Object.entries(c.departments).map(([dept, v]: any) => (
              <tr key={dept}><td>{dept}</td><td>{v.resolved_within_sla_pct ?? "–"}%</td><td>{v.resolved_count}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <b>Ward hotspot density</b> (binned, ~100m grid)
        {h && <HotspotMap bins={h.bins} />}
      </div>
    </>
  );
}
