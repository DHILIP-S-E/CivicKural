"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import PhoneLogin from "@/components/PhoneLogin";
import { completeNewPassword, roleHome, signIn } from "@/lib/auth";
import { setCitizenSession } from "@/lib/citizenSession";

function LoginContent() {
  const params = useSearchParams();
  const [mode, setMode] = useState<"citizen"|"staff">(params.get("mode") === "staff" ? "staff" : "citizen");
  const [username,setUsername]=useState(""); const [password,setPassword]=useState("");
  const [newPassword,setNewPassword]=useState(""); const [confirmPassword,setConfirmPassword]=useState("");
  const [challengeSession,setChallengeSession]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const requested=params.get("next")||"/citizen"; const citizenNext=requested.startsWith("/")&&!requested.startsWith("//")?requested:"/citizen";

  function citizenVerified(token:string){setCitizenSession(token);location.replace(citizenNext);}
  async function staffSubmit(event:FormEvent){event.preventDefault();setBusy(true);setError("");try{if(challengeSession){if(newPassword!==confirmPassword)throw new Error("The new passwords do not match.");const session=await completeNewPassword(username,newPassword,challengeSession);location.replace(roleHome(session.role));return;}const result=await signIn(username.trim(),password);if(result.status==="new_password_required"){setChallengeSession(result.challengeSession);setPassword("");}else location.replace(roleHome(result.session.role));}catch(cause:any){setError(cause.message||"Unable to sign in.");}finally{setBusy(false)}}

  return <div className="auth-layout">
    <section className="auth-story"><div className="eyebrow light">ONE SECURE ACCESS POINT</div><h1>One login. The correct panel.</h1><p>WardWatch verifies your identity and opens only the Citizen, Officer, Coordinator, or Administrator workspace assigned to you.</p><div className="trust-list"><span><b>01</b> India-only citizen phone verification</span><span><b>02</b> Secure staff identity and password</span><span><b>03</b> Role determined by the verified account</span></div></section>
    <section className="auth-panel"><div className="auth-card"><div className="brand-mark large">கு</div><div className="login-tabs" role="tablist"><button type="button" className={mode==="citizen"?"active":""} onClick={()=>{setMode("citizen");setError("")}}>Citizen · WhatsApp OTP</button><button type="button" className={mode==="staff"?"active":""} onClick={()=>{setMode("staff");setError("")}}>Staff · Email & Password</button></div>
      {mode==="citizen"?<PhoneLogin tenantId="MDU-W14" onVerified={citizenVerified} title="Citizen login / registration" description="Enter your Indian mobile number. We'll send the login code through WhatsApp."/>:<div><div className="eyebrow">MUNICIPAL STAFF</div><h2>{challengeSession?"Set your permanent password":"Secure staff sign in"}</h2><p>Your verified account role decides which panel opens.</p><form className="form-stack" onSubmit={staffSubmit}>{!challengeSession?<><label>Email ID or username<input type="text" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} placeholder="name@municipality.gov.in" required/></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password" required/></label></>:<><label>New password<input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={e=>setNewPassword(e.target.value)} required/></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} required/></label><small>Use at least 12 characters with uppercase, lowercase, number, and symbol.</small></>}{error&&<div className="alert error" role="alert">{error}</div>}<button className="button full" disabled={busy}>{busy?"Authenticating…":challengeSession?"Save password & open panel":"Sign in & open my panel →"}</button></form></div>}
      <div className="auth-help"><Link href="/public">Continue to public information without login</Link></div>
    </div></section>
  </div>;
}

export default function Login(){return <Suspense fallback={<div className="state-card">Loading secure login…</div>}><LoginContent/></Suspense>}
