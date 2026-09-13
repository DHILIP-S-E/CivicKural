"use client";

import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

type Bin = { lat: number; lng: number; count: number };

// Ward-14 (Madurai) fallback centre
const DEFAULT_CENTER: [number, number] = [9.9252, 78.1198];

function colorFor(count: number): string {
  if (count >= 10) return "#ef4444"; // Red - high cluster
  if (count >= 5) return "#f59e0b"; // Amber
  if (count >= 2) return "#3b82f6"; // Sapphire
  return "#10b981"; // Emerald
}

function radiusFor(count: number): number {
  return Math.min(8 + count * 2.5, 26);
}

export default function HotspotMap({ bins }: { bins: Bin[] }) {
  const center: [number, number] = bins && bins.length > 0
    ? [bins[0].lat, bins[0].lng]
    : DEFAULT_CENTER;

  return (
    <div>
      <div
        style={{
          height: "440px",
          width: "100%",
          borderRadius: "var(--radius-md)",
          overflow: "hidden",
          border: "1px solid var(--line)",
          boxShadow: "var(--shadow-sm)",
          position: "relative",
          zIndex: 1,
        }}
      >
        <MapContainer center={center} zoom={14} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {bins.map((b, i) => (
            <CircleMarker
              key={i}
              center={[b.lat, b.lng]}
              radius={radiusFor(b.count)}
              pathOptions={{
                color: colorFor(b.count),
                fillColor: colorFor(b.count),
                fillOpacity: 0.65,
                weight: 2,
              }}
            >
              <Tooltip>
                <div style={{ fontFamily: "var(--font-sans)", padding: 4 }}>
                  <strong style={{ display: "block", fontSize: 13 }}>~100m Area Bin</strong>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>{b.count} community report(s)</span>
                </div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "10px 16px",
          marginTop: "12px",
          padding: "10px 14px",
          background: "var(--bg-subtle)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--line)",
          fontSize: "12px",
          fontWeight: 600,
        }}
      >
        <span style={{ color: "var(--ink)", textTransform: "uppercase", letterSpacing: "0.05em", fontSize: 11 }}>
          Cluster Density:
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981", display: "inline-block" }} />
          1 report
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#3b82f6", display: "inline-block" }} />
          2–4 reports
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />
          5–9 reports
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
          10+ critical hotspot
        </span>
      </div>
    </div>
  );
}
