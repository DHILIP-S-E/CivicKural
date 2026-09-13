"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

const HotspotMap = dynamic(() => import("./HotspotMap"), { ssr: false });

export default function PublicPage() {
  const [c, setC] = useState<any>(null);
  const [h, setH] = useState<any>(null);
  const [d, setD] = useState<any>(null);
  const [p, setP] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.compliance(),
      api.hotspots(),
      api.dashboard(),
      api.communityPriorities(),
    ])
      .then(([compliance, hotspots, dashboard, priorities]) => {
        setC(compliance);
        setH(hotspots);
        setD(dashboard);
        setP(priorities.issues);
      })
      .catch((e) => setError(friendlyError(e)));
  }, []);

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            Open Civic Governance
          </div>
          <h1>Public Accountability & Service Transparency</h1>
          <p>
            Real-time public performance metrics without ever compromising citizen privacy. Verifiable department service levels, community priorities, and resolution rates.
          </p>
        </div>
        <Link className="button" href="/login?mode=citizen&next=%2Freport">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14" />
            <path d="M5 12h14" />
          </svg>
          Report an Issue
        </Link>
      </div>

      {error && (
        <div className="alert error" role="alert">
          <strong>Public data service unavailable:</strong> {error}
        </div>
      )}

      {!d ? (
        <div className="state-card">
          <span className="spinner" />
          Aggregating verified ward governance metrics…
        </div>
      ) : (
        <>
          <div className="kpis">
            <div className="kpi open-kpi">
              <span className="metric-label">Reports Received</span>
              <b>{d.total}</b>
              <span className="trend" style={{ color: "var(--blue)" }}>
                Citizen voice captured
              </span>
            </div>
            <div className="kpi resolved-kpi">
              <span className="metric-label">Resolution Rate</span>
              <b>{Math.round(d.resolution_rate * 100)}%</b>
              <span className="trend" style={{ color: "var(--emerald)" }}>
                Verified field outcomes
              </span>
            </div>
            <div className="kpi progress-kpi">
              <span className="metric-label">Median First Action</span>
              <b>
                {d.success_metrics.median_first_action_hours ?? "—"}
                <small style={{ fontSize: 18, textTransform: "none" }}>h</small>
              </b>
              <span className="trend" style={{ color: "var(--amber)" }}>
                Dispatch response velocity
              </span>
            </div>
            <div className="kpi verify-kpi">
              <span className="metric-label">Precise GPS Pinning</span>
              <b>{d.success_metrics.gps_precise_pct}%</b>
              <span className="trend" style={{ color: "var(--purple)" }}>
                High routing confidence
              </span>
            </div>
          </div>

          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h3>Ward Hotspot Density</h3>
                  <p>Privacy-safe ~100m spatial clusters aggregated without pinpointing homes</p>
                </div>
                <span className="badge resolved">
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--emerald)", display: "inline-block" }} />
                  Live Aggregate
                </span>
              </div>
              {h && <HotspotMap bins={h.bins} />}
            </section>

            <aside className="panel">
              <div className="panel-head">
                <div>
                  <h3>Community Priorities</h3>
                  <p>Aggregated signals ranked by civic impact</p>
                </div>
              </div>
              <div style={{ display: "grid", gap: 12 }}>
                {p.slice(0, 6).map((issue, index) => (
                  <div className="flag" key={`${issue.category}-${index}`}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span className={`badge ${issue.priority}`}>
                        #{index + 1} · {issue.priority}
                      </span>
                      <small style={{ fontWeight: 700, color: "var(--ink-secondary)" }}>
                        {issue.report_count} reports
                      </small>
                    </div>
                    <p style={{ textTransform: "capitalize", marginTop: 8 }}>
                      {issue.category.replaceAll("_", " ")}
                    </p>
                    <small>
                      {issue.open_count} open in {issue.area}
                    </small>
                  </div>
                ))}
              </div>
            </aside>
          </div>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h3>Department SLA Performance</h3>
                <p>Objective service delivery compliance. Zero personal scorecards; pure institutional accountability.</p>
              </div>
              <span className="badge open">
                🛡 {d.success_metrics.auto_deduplicated_pct}% duplicates prevented
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Department</th>
                    <th>Resolved within SLA</th>
                    <th>Resolved Cases</th>
                    <th>Critical SLA Breaches</th>
                    <th>Compliance Bar</th>
                  </tr>
                </thead>
                <tbody>
                  {c &&
                    Object.entries(c.departments).map(([dept, value]: any) => {
                      const pct = value.resolved_within_sla_pct ?? 0;
                      return (
                        <tr key={dept}>
                          <td>
                            <b style={{ color: "var(--ink)" }}>{dept}</b>
                          </td>
                          <td>
                            <span style={{ fontWeight: 700, color: pct >= 80 ? "var(--emerald)" : "var(--amber-dark)" }}>
                              {value.resolved_within_sla_pct ?? "—"}%
                            </span>
                          </td>
                          <td>{value.resolved_count}</td>
                          <td>
                            <span style={{ color: (value.tier3_breach_count ?? 0) > 0 ? "var(--red)" : "inherit", fontWeight: (value.tier3_breach_count ?? 0) > 0 ? 700 : 400 }}>
                              {value.tier3_breach_count ?? 0}
                            </span>
                          </td>
                          <td style={{ minWidth: 160 }}>
                            <div className="progress-bar">
                              <span style={{ width: `${pct}%` }} />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </section>

          <div className="privacy-note">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <strong>Citizen Privacy Guarantee</strong>
            </div>
            Civic Kural operates with strict zero-PII retention on open surfaces. This public dashboard will never disclose names, phone numbers, exact citizen addresses, raw media, voice notes, or individual officer scorecards.
          </div>
        </>
      )}
    </>
  );
}
