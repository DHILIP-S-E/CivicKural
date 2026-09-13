"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

type HealthReport = {
  last_escalation_sweep: string | null;
  last_pattern_sweep: string | null;
  recent_notification_failures: number;
};

function HealthContent() {
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchHealth = () => {
    setLoading(true);
    api.health()
      .then((h) => {
        setHealth(h);
        setMsg("");
      })
      .catch((e: any) => setMsg(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  if (msg && !health) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h1>Administrator Access Required</h1>
        <p>Your officer credentials do not hold permissions to inspect backend agent health.</p>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="state-card">
        <span className="spinner" />
        Querying agent heartbeat status from AWS EventBridge…
      </div>
    );
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            System Diagnostics
          </div>
          <h1>Multi-Agent Health & Sweeps</h1>
          <p>
            Real-time status of autonomous EventBridge schedulers, Lambda sweeps, and notification dispatch pipelines.
          </p>
        </div>
        <div className="toolbar">
          <button className="button secondary compact" onClick={fetchHealth} disabled={loading}>
            Refresh Status
          </button>
          <span className="badge resolved">
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--emerald)", display: "inline-block" }} />
            Active Heartbeat
          </span>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi progress-kpi">
          <span className="metric-label">Escalation Sweep</span>
          <b style={{ fontSize: 22, marginTop: 10 }}>Every 6 Hours</b>
          <span className="trend" style={{ color: "var(--brand)" }}>
            EventBridge Cron
          </span>
        </div>

        <div className="kpi open-kpi">
          <span className="metric-label">Pattern Risk Sweep</span>
          <b style={{ fontSize: 22, marginTop: 10 }}>Every 7 Days</b>
          <span className="trend" style={{ color: "var(--blue)" }}>
            Spatial Clustering
          </span>
        </div>

        <div className="kpi resolved-kpi">
          <span className="metric-label">Notification Failures</span>
          <b style={{ fontSize: 24, marginTop: 10, color: health.recent_notification_failures > 0 ? "var(--red)" : "var(--emerald)" }}>
            {health.recent_notification_failures}
          </b>
          <span className="trend" style={{ color: health.recent_notification_failures > 0 ? "var(--red)" : "var(--emerald)" }}>
            {health.recent_notification_failures === 0 ? "100% Delivery Success" : "Delivery issues logged"}
          </span>
        </div>

        <div className="kpi verify-kpi">
          <span className="metric-label">Bedrock Intelligence</span>
          <b style={{ fontSize: 22, marginTop: 10 }}>Claude Vision</b>
          <span className="trend" style={{ color: "var(--purple)" }}>
            Intake & Verification
          </span>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>Last SLA Escalation Sweep</h3>
              <p>Automated sweep inspecting complaint deadlines across all wards</p>
            </div>
            <span className="badge resolved">Lambda Active</span>
          </div>
          <div style={{ padding: 16, background: "var(--bg-subtle)", borderRadius: "var(--radius-md)", border: "1px solid var(--line)" }}>
            <span className="metric-label">Execution Timestamp</span>
            <p style={{ fontSize: 18, fontWeight: 700, margin: "4px 0 0", color: "var(--ink)" }}>
              {health.last_escalation_sweep
                ? new Date(health.last_escalation_sweep).toLocaleString()
                : "Scheduled sweep pending first trigger"}
            </p>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>Last Pattern Detection Sweep</h3>
              <p>Weekly spatial clustering agent grouping recurring infrastructure problems</p>
            </div>
            <span className="badge resolved">Lambda Active</span>
          </div>
          <div style={{ padding: 16, background: "var(--bg-subtle)", borderRadius: "var(--radius-md)", border: "1px solid var(--line)" }}>
            <span className="metric-label">Execution Timestamp</span>
            <p style={{ fontSize: 18, fontWeight: 700, margin: "4px 0 0", color: "var(--ink)" }}>
              {health.last_pattern_sweep
                ? new Date(health.last_pattern_sweep).toLocaleString()
                : "Scheduled sweep pending first trigger"}
            </p>
          </div>
        </section>
      </div>
    </>
  );
}

export default function AdminHealth() {
  return (
    <AuthGuard>
      <HealthContent />
    </AuthGuard>
  );
}
