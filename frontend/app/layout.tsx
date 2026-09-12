import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata = { title: "WardWatch", description: "Civic complaint tracking" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <strong>WardWatch</strong>
          <nav>
            <Link href="/">Queue</Link>
            <Link href="/report">Report an issue</Link>
            <Link href="/escalations">Escalations</Link>
            <Link href="/settings">Settings</Link>
            <Link href="/public">Public</Link>
            <Link href="/login">Sign in</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
