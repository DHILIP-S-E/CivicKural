import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Civic Kural · குடிமக்கள் குரல் | Civic Voice & Autonomous Ward Accountability",
  description: "Autonomous civic complaint intake, multi-agent deduplication, SLA tracking, and public governance transparency.",
  keywords: ["Civic Kural", "Civic Tech", "Ward Accountability", "Madurai", "SLA Tracking", "Citizen Reporting"],
  authors: [{ name: "Civic Kural Governance Network" }],
};

export const viewport: Viewport = {
  themeColor: "#059669",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
