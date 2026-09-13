// Citizen (phone/OTP) session storage — mirrors the expiry-check pattern used
// by lib/auth.ts for officer sessions, but is fully separate: a distinct
// localStorage key and no shared code paths. Officers and citizens must never
// share storage or logic.

const CITIZEN_SESSION_KEY = "ww_citizen_session";

// Backend PhoneSession TTL is ~30 days (per the concurrent backend change).
// The confirm-OTP response only returns `session_token`, with no expiry
// field, so we track a client-side expiry defaulting to 30 days from the
// moment the session is confirmed. This is an approximation of the real
// server-side TTL — if the backend ever starts returning an explicit expiry,
// prefer that instead.
const DEFAULT_CITIZEN_SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export type CitizenSession = {
  token: string;
  expiresAt: number;
};

export function setCitizenSession(token: string, expiresAt?: number) {
  if (typeof window === "undefined") return;
  const session: CitizenSession = {
    token,
    expiresAt: expiresAt ?? Date.now() + DEFAULT_CITIZEN_SESSION_TTL_MS,
  };
  try {
    window.localStorage.setItem(CITIZEN_SESSION_KEY, JSON.stringify(session));
    window.dispatchEvent(new Event("wardwatch-citizen-auth"));
  } catch {
    /* ignore */
  }
}

export function getCitizenSession(): CitizenSession | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(CITIZEN_SESSION_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

export function clearCitizenSession() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(CITIZEN_SESSION_KEY);
    window.dispatchEvent(new Event("wardwatch-citizen-auth"));
  } catch {
    /* ignore */
  }
}

export function isCitizenSessionValid(): boolean {
  const session = getCitizenSession();
  return !!session && !!session.token && session.expiresAt > Date.now();
}
