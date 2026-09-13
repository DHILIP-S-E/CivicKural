import { ensureFreshSession, getAccessToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function getToken(): string {
  return getAccessToken();
}

export function setToken(t: string) {
  // Kept as a no-op compatibility export for older callers.
}

export function setCitizenToken(id: string, token: string) {
  try { window.localStorage.setItem(`ww_citizen_${id}`, token); } catch { /* ignore */ }
}

function getCitizenToken(id: string): string {
  if (typeof window === "undefined") return "";
  try { return window.localStorage.getItem(`ww_citizen_${id}`) ?? ""; } catch { return ""; }
}

async function req(path: string, init: RequestInit = {}, auth = true) {
  if (auth) await ensureFreshSession();
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as any) };
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`;
  const res = await fetch(`${BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// Multipart requests never set Content-Type manually — the browser sets the
// boundary — and are never Cognito-authenticated (public citizen-facing
// endpoints), though some accept a citizen phone-session header instead.
async function reqForm(path: string, form: FormData, method = "POST", headers: Record<string, string> = {}) {
  const res = await fetch(`${BASE}${path}`, { method, body: form, headers, cache: "no-store" });
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
  submitAuthority: (ward: string, id: string) =>
    req(`/complaints/${ward}/${id}/authority-submit`, { method: "POST", body: JSON.stringify({ approved: true }) }),
  authorityStatus: (ward: string, id: string, status: string) =>
    req(`/complaints/${ward}/${id}/authority-status`, { method: "POST", body: JSON.stringify({ status }) }),
  infraFlags: (ward: string) => req(`/complaints/${ward}/infra-flags`),
  settings: () => req(`/admin/settings`),
  saveSettings: (cfg: unknown) => req(`/admin/settings`, { method: "PUT", body: JSON.stringify(cfg) }),
  health: () => req(`/admin/health`),
  compliance: () => req(`/public/compliance`, {}, false),
  hotspots: () => req(`/public/hotspots`, {}, false),
  dashboard: () => req(`/public/dashboard`, {}, false),
  communityPriorities: () => req(`/public/community-priorities`, {}, false),
};

export function getDashboard() {
  return req(`/public/dashboard`, {}, false);
}

export function getComplaintDetail(id: string) {
  return req(`/public/complaints/${id}`, { headers: { "X-Citizen-Token": getCitizenToken(id) } }, false);
}

// Converts a file's bytes to base64 without spreading the whole typed array
// into function arguments — btoa(String.fromCharCode(...bytes)) throws
// RangeError: Maximum call stack size exceeded for any real-world photo over
// ~100KB. Chunking keeps each String.fromCharCode call well under the limit.
export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunkSize = 8192;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

export function verifyResolution(id: string, confirmed: boolean, photo?: File | null) {
  return (async () => {
    let new_photo_b64: string | undefined;
    if (photo) {
      new_photo_b64 = await fileToBase64(photo);
    }
    return req(
      `/public/complaints/${id}/verify-resolution`,
      { method: "POST", headers: { "X-Citizen-Token": getCitizenToken(id) }, body: JSON.stringify({ confirmed, new_photo_b64 }) },
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
  // Verified-phone session token, sent as X-Phone-Session. The backend now
  // derives the reporting phone number from this session instead of a
  // contact_phone form field.
  phoneSessionToken: string;
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
  return reqForm(`/public/reports`, form, "POST", { "X-Phone-Session": params.phoneSessionToken });
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

export async function supportComplaint(reference: string, photo?: File | null) {
  const form = new FormData();
  if (photo) form.append("photo", photo);
  return reqForm(`/public/community/${reference}/support`, form);
}

export function requestPhoneOtp(tenantId: string, phone: string) {
  return req(`/public/verify-phone/request`, { method: "POST", body: JSON.stringify({ tenant_id: tenantId, phone }) }, false);
}

export async function confirmPhoneOtp(tenantId: string, phone: string, code: string): Promise<string> {
  const res = await req(
    `/public/verify-phone/confirm`,
    { method: "POST", body: JSON.stringify({ tenant_id: tenantId, phone, code }) },
    false
  );
  return res.session_token;
}

export function getMyReports(tenantId: string, sessionToken: string) {
  return req(
    `/public/my-reports?tenant_id=${encodeURIComponent(tenantId)}`,
    { headers: { "X-Phone-Session": sessionToken } },
    false
  );
}
