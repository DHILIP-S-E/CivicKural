"use client";
import { useState } from "react";
import { setToken } from "@/lib/api";

export default function Login() {
  const [t, setT] = useState("");
  return (
    <div className="card">
      <h2>Sign in</h2>
      <p>Paste a dev token from <code>python -m wardwatch.devtools token officer MDU-W14</code>.</p>
      <textarea value={t} onChange={(e) => setT(e.target.value)} rows={4} style={{ width: "100%" }} />
      <p>
        <button onClick={() => { setToken(t.trim()); location.href = "/"; }}>Save token</button>
      </p>
    </div>
  );
}
