export function relativeTime(iso: string, now: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)} d ago`;
  return new Date(t).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function fullDate(iso: string): string {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? "" : new Date(t).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function initials(email: string): string {
  const name = email.split("@")[0] ?? "";
  const bits = name.split(/[._-]+/).filter(Boolean);
  return ((bits[0]?.[0] ?? "?") + (bits[1]?.[0] ?? "")).toUpperCase();
}

const LABELS: Record<string, string> = {
  login: "Signed in", login_failed: "Failed sign-in", register_org: "Organisation created", create_group: "Group created",
  create_user: "User created", set_user_groups: "Group membership changed", submit_document: "Document uploaded",
  ingest_done: "Document processed", query: "Question asked", query_error: "Question failed", graph_view: "Graph viewed",
  entity_view: "Entity viewed",
};
export const actionLabel = (a: string): string => LABELS[a] ?? a.replace(/_/g, " ");

/** One-line human summary of an audit event's JSON detail. */
export function describeAudit(action: string, d: Record<string, unknown>): string {
  const s = (k: string) => (typeof d[k] === "string" ? (d[k] as string) : "");
  const arr = (k: string) => (Array.isArray(d[k]) ? (d[k] as unknown[]) : []);
  switch (action) {
    case "query": return `“${s("question")}” · ${arr("chunk_ids").length} sources${arr("violations").length ? " · output blocked/edited" : ""}${arr("dropped_chunks").length ? " · quarantined content skipped" : ""}`;
    case "query_error": return `“${s("question")}” · ${s("error")}`;
    case "submit_document": return `${s("title")} → ${arr("groups").join(", ") || "admins only"}`;
    case "ingest_done": return `document #${String(d["doc_id"] ?? "?")} · ${String(d["flagged_chunks"] ?? 0)} chunk(s) quarantined`;
    case "create_user": return `${s("email")} (${s("role")}) in ${arr("groups").join(", ") || "no groups"}`;
    case "set_user_groups": return `${s("user")} → ${arr("groups").join(", ") || "no groups"}`;
    case "create_group": return s("group");
    case "login_failed": return s("email");
    case "register_org": return s("org");
    default: return Object.keys(d).length ? JSON.stringify(d).slice(0, 120) : "";
  }
}
