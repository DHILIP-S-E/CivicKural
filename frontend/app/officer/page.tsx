"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

const WARD = "MDU-W14";
const label = (value: string) => value?.replaceAll("_", " ") || "—";

function Operations() {
  const [rows, setRows] = useState<any[]>([]);
  const [flags, setFlags] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = () => {
    setLoading(true);
    Promise.all([api.queue(WARD), api.infraFlags(WARD)])
      .then(([items, risks]) => {
        setRows(items);
        setFlags(risks);
        setErr("");
      })
      .catch((e) => setErr(friendlyError(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  const visibleRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!filter || row.status === filter) &&
          (!search ||
            `${row.complaint_id} ${row.category} ${row.routed_dept}`
              .toLowerCase()
              .includes(search.toLowerCase()))
      ),
    [rows, filter, search]
  );

  const count = (status: string) => rows.filter((row) => row.status === status).length;
  const escalationCount = rows.filter((row) => row.escalation_tier > 0).length;

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
            Operations Command Center
          </div>
          <h1>Ward {WARD} Operations</h1>
          <p>
            Autonomous triage, SLA enforcement, and multi-agent dispatch. Prioritize urgent citizen concerns before service level agreements are breached.
          </p>
        </div>
        <div className="toolbar">
          <button className="button secondary compact" onClick={fetchData} title="Refresh case queue" disabled={loading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={loading ? "spinner" : ""}>
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
              <path d="M16 21h5v-5" />
            </svg>
            Refresh
          </button>
          <Link className="button" href="/report">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            New Citizen Report
          </Link>
        </div>
      </div>

      {err && (
        <div className="alert error" role="alert">
          <strong>Queue synchronization failure:</strong> {err} Your session may have expired.{" "}
          <Link href="/login" style={{ textDecoration: "underline", fontWeight: 700 }}>
            Sign in again
          </Link>
          .
        </div>
      )}

      <div className="kpis">
        <div className="kpi open-kpi">
          <span className="metric-label">Open Reports</span>
          <b>{count("open")}</b>
          <span className="trend" style={{ color: "var(--blue)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--blue)", display: "inline-block" }} />
            Awaiting triage / assignment
          </span>
        </div>
        <div className="kpi progress-kpi">
          <span className="metric-label">In Progress</span>
          <b>{count("in_progress")}</b>
          <span className="trend" style={{ color: "var(--amber)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--amber)", display: "inline-block" }} />
            Field teams dispatched
          </span>
        </div>
        <div className="kpi verify-kpi">
          <span className="metric-label">Verification</span>
          <b>{count("pending_verification")}</b>
          <span className="trend" style={{ color: "var(--purple)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--purple)", display: "inline-block" }} />
            AI & Citizen evidence review
          </span>
        </div>
        <div className="kpi escalation-kpi">
          <span className="metric-label">SLA Escalations</span>
          <b style={{ color: escalationCount > 0 ? "var(--red)" : "inherit" }}>{escalationCount}</b>
          <span className="trend">
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: escalationCount > 0 ? "var(--red)" : "var(--emerald)", display: "inline-block" }} />
            {escalationCount > 0 ? "Requires supervisor action" : "All SLAs on track"}
          </span>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>Live Case Queue</h3>
              <p>
                Showing {visibleRows.length} of {rows.length} reports for Ward {WARD}
              </p>
            </div>
            <div className="toolbar" style={{ gap: 8 }}>
              {["", "open", "in_progress", "pending_verification", "resolved"].map((statusKey) => {
                const countNum = statusKey === "" ? rows.length : count(statusKey);
                const isSelected = filter === statusKey;
                return (
                  <button
                    key={statusKey}
                    type="button"
                    onClick={() => setFilter(statusKey)}
                    className={`button compact ${isSelected ? "" : "ghost"}`}
                    style={{ fontSize: 12, padding: "5px 10px" }}
                  >
                    {statusKey === "" ? "All" : label(statusKey)} ({countNum})
                  </button>
                );
              })}
            </div>
          </div>

          <div className="toolbar" style={{ marginBottom: 18 }}>
            <div className="search-box">
              <span className="search-icon" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
              </span>
              <input
                aria-label="Search cases"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by Case ID, Category, or Department…"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    color: "var(--muted)",
                    padding: 4,
                    cursor: "pointer",
                    boxShadow: "none",
                  }}
                  aria-label="Clear search"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {loading ? (
            <div className="state-card">
              <span className="spinner" />
              Synchronizing live case queue from DynamoDB…
            </div>
          ) : visibleRows.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <h3>No matching cases</h3>
              <p>There are no reports matching the current filter in this ward.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Case ID</th>
                    <th>Issue & Severity</th>
                    <th>Priority</th>
                    <th>Department</th>
                    <th>SLA Deadline</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => {
                    const isOverdue = new Date(row.sla_deadline) < new Date() && row.status !== "resolved";
                    return (
                      <tr key={row.complaint_id}>
                        <td>
                          <Link
                            className="id-link"
                            href={`/complaints?ward=${encodeURIComponent(WARD)}&id=${encodeURIComponent(row.complaint_id)}`}
                          >
                            #{row.complaint_id.slice(-8)}
                          </Link>
                        </td>
                        <td>
                          <b style={{ textTransform: "capitalize", color: "var(--ink)" }}>{label(row.category)}</b>
                          <br />
                          <small style={{ color: "var(--muted)" }}>{label(row.severity)} severity</small>
                        </td>
                        <td>
                          <span className={`badge ${row.priority}`}>{label(row.priority)}</span>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: "var(--ink-secondary)" }}>{row.routed_dept}</span>
                        </td>
                        <td>
                          <span style={{ color: isOverdue ? "var(--red)" : "inherit", fontWeight: isOverdue ? 700 : 500 }}>
                            {new Date(row.sla_deadline).toLocaleDateString()}
                          </span>
                          {isOverdue && (
                            <span style={{ marginLeft: 6, fontSize: 11, color: "var(--red)", fontWeight: 700 }}>
                              ⚠ Breach
                            </span>
                          )}
                        </td>
                        <td>
                          <span className={`badge ${row.status}`}>{label(row.status)}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="panel">
          <div className="panel-head">
            <div>
              <h3>Infrastructure Signals</h3>
              <p>Clustered patterns detected over 90 days</p>
            </div>
            <span className="badge resolved" style={{ fontSize: 11 }}>
              PatternAgent Active
            </span>
          </div>
          {flags.length ? (
            flags.map((flag) => (
              <div className="flag" key={flag.flag_id}>
                <p>{flag.summary}</p>
                <small>
                  {flag.incident_count} {label(flag.category)} reports · {flag.window_days} day cluster window
                </small>
              </div>
            ))
          ) : (
            <div className="empty-state" style={{ padding: "36px 18px" }}>
              <div className="empty-icon" style={{ width: 44, height: 44, fontSize: 20 }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <path d="m4.93 4.93 4.24 4.24" />
                  <path d="m14.83 9.17 4.24-4.24" />
                  <path d="m14.83 14.83 4.24 4.24" />
                  <path d="m9.17 14.83-4.24 4.24" />
                </svg>
              </div>
              <h3>No Pattern Anomalies</h3>
              <p>Weekly multi-agent cluster detector has not identified recurring failure zones in this ward.</p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}

export default function OfficerPanel() {
  return (
    <AuthGuard roles={["officer", "coordinator"]}>
      <Operations />
    </AuthGuard>
  );
}
