"use client";

import { useEffect, useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

function MapEditor({
  title,
  description,
  value,
  onChange,
  type = "text",
}: {
  title: string;
  description: string;
  value: Record<string, any>;
  onChange: (v: any) => void;
  type?: string;
}) {
  const entries = Object.entries(value || {});

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        <button
          type="button"
          className="button secondary compact"
          onClick={() =>
            onChange({
              ...value,
              [`new_rule_${entries.length + 1}`]: type === "number" ? 1 : "",
            })
          }
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Rule
        </button>
      </div>

      <div className="form-stack">
        {entries.length === 0 ? (
          <div className="empty-state" style={{ padding: 24, fontSize: 13.5 }}>
            No custom overrides active. Ward default policy applies.
          </div>
        ) : (
          entries.map(([key, val], index) => (
            <div className="form-grid" key={index} style={{ alignItems: "flex-end" }}>
              <label>
                Rule Key
                <input
                  value={key}
                  onChange={(e) => {
                    const next = { ...value };
                    delete next[key];
                    next[e.target.value] = val;
                    onChange(next);
                  }}
                  placeholder="e.g. pothole"
                />
              </label>
              <label>
                Value
                <div className="toolbar" style={{ marginTop: 6 }}>
                  <input
                    type={type}
                    min={type === "number" ? 0 : undefined}
                    value={val}
                    onChange={(e) =>
                      onChange({
                        ...value,
                        [key]: type === "number" ? Number(e.target.value) : e.target.value,
                      })
                    }
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="button ghost compact"
                    aria-label={`Remove rule ${key}`}
                    onClick={() => {
                      const next = { ...value };
                      delete next[key];
                      onChange(next);
                    }}
                    style={{ color: "var(--red)" }}
                  >
                    Remove
                  </button>
                </div>
              </label>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function SettingsContent() {
  const [cfg, setCfg] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.settings()
      .then(setCfg)
      .catch((e) => setMsg(friendlyError(e)));
  }, []);

  if (msg && !cfg) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>
        <h1>Administrator Access Required</h1>
        <p>Your officer credentials do not possess policy configuration permissions for this tenant.</p>
      </div>
    );
  }

  if (!cfg) {
    return (
      <div className="state-card">
        <span className="spinner" />
        Loading tenant policy configuration…
      </div>
    );
  }

  async function save() {
    setSaving(true);
    setMsg("");
    try {
      await api.saveSettings(cfg);
      setMsg("Policy configuration updated and cryptographically audit-logged.");
    } catch (e: any) {
      setMsg(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-content">
          <div className="eyebrow">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            Tenant Administration
          </div>
          <h1>Policy & SLA Routing</h1>
          <p>
            Configure how {cfg.tenant_id} assigns department routing, SLA deadlines, and priority multipliers.
          </p>
        </div>
        <button className="button" onClick={save} disabled={saving}>
          {saving ? (
            <>
              <span className="spinner" />
              Saving Policy…
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                <polyline points="17 21 17 13 7 13 7 21" />
                <polyline points="7 3 7 8 15 8" />
              </svg>
              Save Policy Changes
            </>
          )}
        </button>
      </div>

      {msg && (
        <div
          className={`alert ${msg.includes("updated") ? "success" : "error"}`}
          role={msg.includes("updated") ? "status" : "alert"}
          style={{ marginBottom: 20 }}
        >
          {msg}
        </div>
      )}

      <div className="dashboard-grid">
        <div>
          <MapEditor
            title="Service-Level Commitments (SLA)"
            description="Category-specific deadline in calendar days (1–365) before automated escalation triggers."
            value={cfg.sla_overrides}
            type="number"
            onChange={(v) => setCfg({ ...cfg, sla_overrides: v })}
          />

          <MapEditor
            title="Department Routing Rules"
            description="Explicitly maps issue categories to municipal response divisions."
            value={cfg.routing_overrides}
            onChange={(v) => setCfg({ ...cfg, routing_overrides: v })}
          />

          <MapEditor
            title="Notification Alert Endpoints"
            description="Official department contact email or webhook destinations for escalation notifications."
            value={cfg.dept_contacts}
            onChange={(v) => setCfg({ ...cfg, dept_contacts: v })}
          />
        </div>

        <aside>
          <MapEditor
            title="Priority Scoring Weights"
            description="Impact coefficients (0–10) applied to vision severity, community size, and proximity."
            value={cfg.priority_weights}
            type="number"
            onChange={(v) => setCfg({ ...cfg, priority_weights: v })}
          />

          <div className="privacy-note">
            <strong>Audit Guarantee</strong>
            <br />
            Every policy override is signed and versioned in the tenant configuration store. SLA deadlines for active complaints are computed deterministically.
          </div>
        </aside>
      </div>
    </>
  );
}

export default function Settings() {
  return (
    <AuthGuard>
      <SettingsContent />
    </AuthGuard>
  );
}
