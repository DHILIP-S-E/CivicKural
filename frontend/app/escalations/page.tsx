"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

const WARD = "MDU-W14";

function EscalationContent() {
  const [rows, setRows] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchEscalations = () => {
    setLoading(true);
    api.queue(WARD)
      .then((r) => setRows(r.filter((x: any) => x.escalation_tier > 0)))
      .catch((e) => setErr(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchEscalations();
  }, []);

  const tier1Count = rows.filter((r) => r.escalation_tier === 1).length;
  const tier2Count = rows.filter((r) => r.escalation_tier === 2).length;
  const tier3Count = rows.filter((r) => r.escalation_tier >= 3).length;
  const totalNotices = rows.reduce((n, r) => n + (r.escalation_count || 0), 0);

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <line x1="12" x2="12" y1="9" y2="13" />
              <line x1="12" x2="12.01" y1="17" y2="17" />
            </svg>
            Service Level Enforcement
          </div>
          <h1>SLA Escalation Center</h1>
          <p>
            Automated multi-tier intervention radar. Cases that exceed legally defined response timeframes are escalated autonomously without human intervention.
          </p>
        </div>
        <div className="toolbar">
          <button className="button secondary compact" onClick={fetchEscalations} disabled={loading}>
            Refresh Radar
          </button>
          <span className={`badge ${rows.length > 0 ? "critical" : "resolved"}`}>
            {rows.length > 0 ? `${rows.length} Active Escalations` : "All SLAs Compliant"}
          </span>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi progress-kpi">
          <span className="metric-label">Tier 1 · Officer Warning</span>
          <b>{tier1Count}</b>
          <span className="trend" style={{ color: "var(--amber)" }}>
            6 hours post-checkpoint
          </span>
        </div>
        <div className="kpi escalation-kpi">
          <span className="metric-label">Tier 2 · Supervisor Alert</span>
          <b style={{ color: tier2Count > 0 ? "#be123c" : "inherit" }}>{tier2Count}</b>
          <span className="trend" style={{ color: "#be123c" }}>
            12 hours post-checkpoint
          </span>
        </div>
        <div className="kpi escalation-kpi">
          <span className="metric-label">Tier 3 · Critical Breach</span>
          <b style={{ color: tier3Count > 0 ? "var(--red)" : "inherit" }}>{tier3Count}</b>
          <span className="trend">
            Immediate Commissioner review
          </span>
        </div>
        <div className="kpi open-kpi">
          <span className="metric-label">Total Escalation Notices</span>
          <b>{totalNotices}</b>
          <span className="trend" style={{ color: "var(--blue)" }}>
            Immutable audit logs
          </span>
        </div>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>Active Escalation Log</h3>
            <p>Ward {WARD} · Synchronized with 6-hourly EventBridge sweep scheduler</p>
          </div>
        </div>

        {err && (
          <div className="alert error" role="alert">
            {err}
          </div>
        )}

        {loading ? (
          <div className="state-card">
            <span className="spinner" />
            Scanning active SLA checkpoints…
          </div>
        ) : rows.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h3>Zero Active Escalations</h3>
            <p>All citizen cases in Ward {WARD} are currently progressing within their committed SLA windows.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case Reference</th>
                  <th>Issue Category</th>
                  <th>Escalation Level</th>
                  <th>Notices Dispatched</th>
                  <th>SLA Deadline</th>
                  <th>Resolution Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.complaint_id}>
                    <td>
                      <Link
                        className="id-link"
                        href={`/complaints?ward=${encodeURIComponent(WARD)}&id=${encodeURIComponent(r.complaint_id)}`}
                      >
                        #{r.complaint_id.slice(-8)}
                      </Link>
                    </td>
                    <td>
                      <b style={{ textTransform: "capitalize", color: "var(--ink)" }}>{r.category.replaceAll("_", " ")}</b>
                    </td>
                    <td>
                      <span className={`badge tier${r.escalation_tier}`}>
                        Tier {r.escalation_tier} Escalation
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 700 }}>{r.escalation_count}</span> notice(s)
                    </td>
                    <td>
                      <span style={{ color: "var(--red)", fontWeight: 700 }}>
                        {new Date(r.sla_deadline).toLocaleString()}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${r.status}`}>
                        {r.resolved_at ? `Resolved: ${new Date(r.resolved_at).toLocaleDateString()}` : "Open / Overdue"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

export default function Escalations() {
  return (
    <AuthGuard roles={["officer", "coordinator"]}>
      <EscalationContent />
    </AuthGuard>
  );
}
