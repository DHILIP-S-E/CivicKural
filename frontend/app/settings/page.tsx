"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Settings() {
  const [cfg, setCfg] = useState<any>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.settings().then(setCfg).catch((e) => setMsg(String(e)));
  }, []);

  if (msg && !cfg) return <div className="card">Admin only. {msg}</div>;
  if (!cfg) return <div className="card">Loading…</div>;

  const edit = (k: string) => (e: any) => {
    try { setCfg({ ...cfg, [k]: JSON.parse(e.target.value) }); } catch { /* keep typing */ }
  };

  return (
    <>
      <h2>Tenant settings — {cfg.tenant_id}</h2>
      <div className="card">
        <p>SLA overrides (category → days)</p>
        <textarea rows={4} style={{ width: "100%" }} defaultValue={JSON.stringify(cfg.sla_overrides, null, 2)} onChange={edit("sla_overrides")} />
        <p>Routing overrides (category → dept)</p>
        <textarea rows={4} style={{ width: "100%" }} defaultValue={JSON.stringify(cfg.routing_overrides, null, 2)} onChange={edit("routing_overrides")} />
        <p>Department contacts (dept → email/phone)</p>
        <textarea rows={4} style={{ width: "100%" }} defaultValue={JSON.stringify(cfg.dept_contacts, null, 2)} onChange={edit("dept_contacts")} />
        <p><button onClick={() => api.saveSettings(cfg).then(() => setMsg("Saved")).catch((e) => setMsg(String(e)))}>Save</button> {msg}</p>
      </div>
    </>
  );
}
