"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import { api } from "@/lib/api";

function CoordinatorContent() {
  const [rows, setRows] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([api.queue("MDU-W14"), api.dashboard()]).then(([cases, dashboard]) => {
      setRows(cases); setMetrics(dashboard);
    }).finally(() => setLoading(false));
  }, []);
  if (loading) return <div className="state-card"><span className="spinner" />Preparing coordinator overview…</div>;
  return <>
    <div className="page-head"><div><div className="eyebrow">READ-ONLY SUPERVISION</div><h1>Coordinator panel</h1><p>Ward-wide visibility for service coordination without operational mutation permissions.</p></div><span className="badge open">Read-only role</span></div>
    <div className="kpis"><div className="kpi"><span className="metric-label">Total cases</span><b>{rows.length}</b><span className="trend">Ward MDU-W14</span></div><div className="kpi"><span className="metric-label">Open</span><b>{rows.filter(r=>r.status==="open").length}</b><span className="trend">Awaiting action</span></div><div className="kpi"><span className="metric-label">Escalated</span><b>{rows.filter(r=>r.escalation_tier>0).length}</b><span className="trend">Service risk</span></div><div className="kpi"><span className="metric-label">Resolution rate</span><b>{Math.round((metrics?.resolution_rate??0)*100)}%</b><span className="trend">Aggregate outcome</span></div></div>
    <div className="dashboard-grid"><section className="panel"><div className="panel-head"><div><h3>Department workload</h3><p>Live cases grouped across the ward</p></div></div><div className="table-wrap"><table><thead><tr><th>Department</th><th>Cases</th><th>Escalated</th></tr></thead><tbody>{Object.entries(rows.reduce((acc:any,row:any)=>{acc[row.routed_dept]??={total:0,escalated:0};acc[row.routed_dept].total++;if(row.escalation_tier>0)acc[row.routed_dept].escalated++;return acc;},{})).map(([dept,value]:any)=><tr key={dept}><td><b>{dept}</b></td><td>{value.total}</td><td>{value.escalated}</td></tr>)}</tbody></table></div></section><aside className="panel"><div className="panel-head"><div><h3>Coordinator tools</h3><p>Read-only oversight views</p></div></div><div className="form-stack"><Link className="button" href="/public">Public performance</Link><Link className="button secondary" href="/officer">View case queue</Link></div><div className="privacy-note" style={{marginTop:18}}><b>Permission boundary</b><br/>Coordinators can inspect case progress but cannot change status, submit authority actions, or edit policy.</div></aside></div>
  </>;
}

export default function CoordinatorPanel(){return <AuthGuard roles={["coordinator"]}><CoordinatorContent/></AuthGuard>}
