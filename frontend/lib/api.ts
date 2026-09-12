const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem("ww_token") ?? "";
  } catch {
    return "";
  }
}

export function setToken(t: string) {
  try {
    window.localStorage.setItem("ww_token", t);
  } catch {
    /* ignore */
  }
}

async function req(path: string, init: RequestInit = {}, auth = true) {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as any) };
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// Multipart requests never set Content-Type manually — the browser sets the
// boundary — and are never authenticated (public citizen-facing endpoints).
async function reqForm(path: string, form: FormData, method = "POST") {
  const res = await fetch(`${BASE}${path}`, { method, body: form, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  queue: (ward: string, status?: string) =>
    req(`/complaints?ward_id=${ward}${status ? `&status=${status}` : ""}`),
  detail: (ward: string, id: string) => req(`/complaints/${ward}/${id}`),
  setStatus: (ward: string, id: string, status: string, note?: string) =>
    req(`/complaints/${ward}/${id}/status`, { method: "POST", body: JSON.stringify({ status, note }) }),
  verify: (ward: string, id: string, after_photo_b64: string) =>
    req(`/complaints/${ward}/${id}/verify`, { method: "POST", body: JSON.stringify({ after_photo_b64 }) }),
  settings: () => req(`/admin/settings`),
  saveSettings: (cfg: unknown) => req(`/admin/settings`, { method: "PUT", body: JSON.stringify(cfg) }),
  compliance: () => req(`/public/compliance`, {}, false),
  hotspots: () => req(`/public/hotspots`, {}, false),
  dashboard: () => req(`/public/dashboard`, {}, false),
};

export function getDashboard() {
  return req(`/public/dashboard`, {}, false);
}

export function getComplaintDetail(id: string) {
  return req(`/public/complaints/${id}`, {}, false);
}

export function verifyResolution(id: string, confirmed: boolean, photo?: File | null) {
  return (async () => {
    let new_photo_b64: string | undefined;
    if (photo) {
      const buf = await photo.arrayBuffer();
      new_photo_b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
    }
    return req(
      `/public/complaints/${id}/verify-resolution`,
      { method: "POST", body: JSON.stringify({ confirmed, new_photo_b64 }) },
      false
    );
  })();
}

export type SubmitReportParams = {
  transcript: string;
  wardId: string;
  lat?: number;
  lng?: number;
  photo?: File | null;
  audio?: File | null;
  video?: File | null;
};

export async function submitReport(params: SubmitReportParams) {
  const form = new FormData();
  form.append("transcript", params.transcript);
  form.append("ward_id", params.wardId);
  if (params.lat !== undefined) form.append("lat", String(params.lat));
  if (params.lng !== undefined) form.append("lng", String(params.lng));
  if (params.photo) form.append("photo", params.photo);
  if (params.audio) form.append("audio", params.audio);
  if (params.video) form.append("video", params.video);
  return reqForm(`/public/reports`, form);
}

export async function getNearbyComplaints(opts: {
  lat: number;
  lng: number;
  category?: string;
  radiusM?: number;
}) {
  const params = new URLSearchParams({
    lat: String(opts.lat),
    lng: String(opts.lng),
    radius_m: String(opts.radiusM ?? 500),
  });
  if (opts.category) params.set("category", opts.category);
  return req(`/public/complaints/nearby?${params.toString()}`, {}, false);
}

export async function supportComplaint(complaintId: string, wardId: string, photo?: File | null) {
  const form = new FormData();
  form.append("ward_id", wardId);
  if (photo) form.append("photo", photo);
  return reqForm(`/public/complaints/${complaintId}/support`, form);
}
