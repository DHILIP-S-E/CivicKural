const REGION = process.env.NEXT_PUBLIC_AWS_REGION ?? "ap-south-1";
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const ENDPOINT = `https://cognito-idp.${REGION}.amazonaws.com/`;

export type Session = {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresAt: number;
  username: string;
  role: "admin" | "officer" | "coordinator";
  tenantId: string;
  wards: string[];
};

export type LoginResult =
  | { status: "authenticated"; session: Session }
  | { status: "new_password_required"; username: string; challengeSession: string };

const SESSION_KEY = "wardwatch_session";

async function cognito(target: string, body: Record<string, unknown>) {
  if (!CLIENT_ID) throw new Error("Authentication is not configured for this deployment.");
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    const message = result.message || result.Message || "Sign-in failed.";
    throw new Error(message.replace(/^[^:]+:\s*/, ""));
  }
  return result;
}

function decodeClaims(idToken: string, fallback: string) {
  try {
    const payload = JSON.parse(atob(idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    const role = ["admin", "officer", "coordinator"].includes(payload["custom:role"])
      ? payload["custom:role"]
      : "officer";
    return {
      username: payload["cognito:username"] || payload.email || fallback,
      role,
      tenantId: payload["custom:tenant_id"] || "MDU-CORP",
      wards: String(payload["custom:wards"] || "").split(",").map((ward) => ward.trim()).filter(Boolean),
    };
  } catch {
    return { username: fallback, role: "officer" as const, tenantId: "MDU-CORP", wards: [] as string[] };
  }
}

function saveAuthentication(result: any, username: string): Session {
  const auth = result.AuthenticationResult;
  const claims = decodeClaims(auth.IdToken, username);
  const session: Session = {
    accessToken: auth.AccessToken,
    idToken: auth.IdToken,
    refreshToken: auth.RefreshToken,
    expiresAt: Date.now() + (auth.ExpiresIn ?? 3600) * 1000,
    ...claims,
  };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("wardwatch-auth"));
  return session;
}

export async function signIn(username: string, password: string): Promise<LoginResult> {
  const result = await cognito("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: CLIENT_ID,
    AuthParameters: { USERNAME: username, PASSWORD: password },
  });
  if (result.ChallengeName === "NEW_PASSWORD_REQUIRED") {
    return { status: "new_password_required", username, challengeSession: result.Session };
  }
  return { status: "authenticated", session: saveAuthentication(result, username) };
}

export async function completeNewPassword(
  username: string,
  newPassword: string,
  challengeSession: string,
) {
  const result = await cognito("RespondToAuthChallenge", {
    ChallengeName: "NEW_PASSWORD_REQUIRED",
    ClientId: CLIENT_ID,
    Session: challengeSession,
    ChallengeResponses: { USERNAME: username, NEW_PASSWORD: newPassword },
  });
  return saveAuthentication(result, username);
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const value = sessionStorage.getItem(SESSION_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

export function getAccessToken() {
  return getSession()?.accessToken ?? "";
}

export function signOut() {
  sessionStorage.removeItem(SESSION_KEY);
  window.dispatchEvent(new Event("wardwatch-auth"));
}

export function isSignedIn() {
  const session = getSession();
  return !!session && session.expiresAt > Date.now();
}

// Consider a token near-expiry if it has less than this much life left, so we
// refresh proactively instead of racing an in-flight API call against expiry.
const EXPIRY_SKEW_MS = 60_000;

export function isExpiredOrNearExpiry(session: Session | null): boolean {
  if (!session) return true;
  return session.expiresAt - EXPIRY_SKEW_MS <= Date.now();
}

async function refreshSession(session: Session): Promise<Session | null> {
  if (!session.refreshToken) return null;
  try {
    const result = await cognito("InitiateAuth", {
      AuthFlow: "REFRESH_TOKEN_AUTH",
      ClientId: CLIENT_ID,
      AuthParameters: { REFRESH_TOKEN: session.refreshToken },
    });
    const auth = result.AuthenticationResult;
    const next: Session = {
      accessToken: auth.AccessToken,
      idToken: auth.IdToken ?? session.idToken,
      // Cognito's refresh-token flow does not reissue a refresh token; keep the existing one.
      refreshToken: session.refreshToken,
      expiresAt: Date.now() + (auth.ExpiresIn ?? 3600) * 1000,
      username: session.username,
      role: session.role,
      tenantId: session.tenantId,
      wards: session.wards,
    };
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
    window.dispatchEvent(new Event("wardwatch-auth"));
    return next;
  } catch {
    return null;
  }
}

// Ensures the stored session has a live access token before it is used,
// silently refreshing it via the refresh token when it's expired or about to
// expire. Clears the session (and signals a "session expired" state) when no
// refresh is possible.
export async function ensureFreshSession(): Promise<Session | null> {
  const session = getSession();
  if (!session) return null;
  if (!isExpiredOrNearExpiry(session)) return session;
  const refreshed = await refreshSession(session);
  if (refreshed) return refreshed;
  signOut();
  return null;
}

export function roleHome(role?: Session["role"]) {
  if (role === "admin") return "/admin";
  if (role === "coordinator") return "/coordinator";
  if (role === "officer") return "/officer";
  return "/";
}
