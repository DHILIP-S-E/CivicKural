import Link from "next/link";

export default function NotFound() {
  return (
    <section className="empty-state lock-state">
      <div className="empty-icon">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="m15 9-6 6" />
          <path d="m9 9 6 6" />
        </svg>
      </div>
      <h1>Page Not Found</h1>
      <p style={{ maxWidth: 460, margin: "8px auto 24px" }}>
        The civic route or case record you requested does not exist or has been relocated within the governance network.
      </p>
      <div className="toolbar" style={{ justifyContent: "center" }}>
        <Link className="button" href="/">
          Return to Operations
        </Link>
        <Link className="button secondary" href="/public">
          View Public Data
        </Link>
      </div>
    </section>
  );
}
