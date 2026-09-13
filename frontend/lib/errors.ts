// Turns the raw `${status} ${bodyText}` Error thrown by lib/api.ts's req()
// helper into a short, readable message for end users instead of a dumped
// HTTP status line or raw JSON body.
export function friendlyError(e: unknown): string {
  const raw = (e as any)?.message ?? String(e ?? "");
  const match = raw.match(/^(\d{3})\s+([\s\S]*)$/);
  if (match) {
    const [, status, body] = match;
    try {
      const parsed = JSON.parse(body);
      const detail = parsed?.detail ?? parsed?.message ?? parsed?.error;
      if (typeof detail === "string" && detail.trim()) return detail;
    } catch {
      /* body wasn't JSON */
    }
    if (status === "401" || status === "403") return "You don't have permission to do that. Please sign in again.";
    if (status === "404") return "We couldn't find that record.";
    if (status === "409") return "That action conflicts with the current state — please refresh and try again.";
    if (status.startsWith("5")) return "Something went wrong on our end. Please try again shortly.";
    return `Request failed (${status}). Please try again.`;
  }
  return raw || "Something went wrong. Please try again.";
}
