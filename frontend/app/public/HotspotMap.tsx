"use client";
import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

type Bin = { lat: number; lng: number; count: number };

// Ward-14 (Madurai) fallback centre — used only when there are no bins yet.
const DEFAULT_CENTER: [number, number] = [9.9252, 78.1198];

function colorFor(count: number): string {
  if (count >= 10) return "#b91c1c"; // red
  if (count >= 5) return "#d97706"; // amber
  if (count >= 2) return "#ca8a04"; // yellow
  return "#2563eb"; // blue
}

function radiusFor(count: number): number {
  return Math.min(6 + count * 2, 24);
}

export default function HotspotMap({ bins }: { bins: Bin[] }) {
  const center: [number, number] = bins.length
    ? [bins[0].lat, bins[0].lng]
    : DEFAULT_CENTER;

  return (
    <div>
      <div style={{ height: "420px", width: "100%", borderRadius: "8px", overflow: "hidden" }}>
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
              pathOptions={{ color: colorFor(b.count), fillColor: colorFor(b.count), fillOpacity: 0.6 }}
            >
              <Tooltip>{b.count} report(s)</Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem", fontSize: "0.9rem" }}>
        <b>Legend:</b>
        <span><span style={{ color: "#2563eb" }}>●</span> 1 report</span>
        <span><span style={{ color: "#ca8a04" }}>●</span> 2-4 reports</span>
        <span><span style={{ color: "#d97706" }}>●</span> 5-9 reports</span>
        <span><span style={{ color: "#b91c1c" }}>●</span> 10+ reports</span>
      </div>
    </div>
  );
}
