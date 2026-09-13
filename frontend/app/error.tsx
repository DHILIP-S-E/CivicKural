"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section className="empty-state lock-state">
      <div className="empty-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h1>Operational Exception Encountered</h1>
      <p style={{ maxWidth: 480, margin: "8px auto 24px" }}>
        Civic Kural encountered an unexpected condition while rendering this page. You can retry the operation or return to the operations console.
      </p>
      <div className="toolbar" style={{ justifyContent: "center" }}>
        <button className="button" onClick={() => reset()}>
          Retry Action
        </button>
        <Link className="button secondary" href="/">
          Return to Operations
        </Link>
      </div>
    </section>
  );
}
