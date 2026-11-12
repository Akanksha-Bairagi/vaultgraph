import type {
  AuditEvent, AuthConfig, Dashboard, DocItem, Group, GraphOverview, Job, Me, QueryOptions, QueryResult, Status,
  Subgraph, UserItem,
} from "../types.ts";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type KV = { getItem(k: string): string | null; setItem(k: string, v: string): void; removeItem(k: string): void };
export interface ClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  storage?: KV;
  onUnauthorized?: () => void;
}
const TOKEN_KEY = "vg_token";

/** Turns FastAPI error bodies ({detail: string} or pydantic's {detail: [{loc, msg}]}) into one readable message. */
export function errorMessage(body: unknown, status: number): { message: string; code?: string } {
  const b = body as { detail?: unknown; code?: string } | null;
  const d = b?.detail;
  if (typeof d === "string") return { message: d, code: b?.code };
  if (Array.isArray(d)) {
    const parts = d.map((x: { loc?: unknown[]; msg?: string }) => {
      const field = Array.isArray(x.loc) ? String(x.loc[x.loc.length - 1]) : "";
      return field && field !== "body" ? `${field}: ${x.msg ?? "invalid"}` : (x.msg ?? "invalid");
    });
    return { message: parts.join("; ") || "Invalid request." };
  }
  if (status === 429) return { message: "Too many requests. Please wait a moment." };
  if (status >= 500) return { message: "The server had a problem. Please try again." };
  return { message: `Request failed (HTTP ${status}).` };
}

export function createClient(opts: ClientOptions = {}) {
  const base = opts.baseUrl ?? "";
  const doFetch = opts.fetchImpl ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
  const store = opts.storage;

  const getToken = () => store?.getItem(TOKEN_KEY) ?? null;
  const setToken = (t: string) => store?.setItem(TOKEN_KEY, t);
  const clearToken = () => store?.removeItem(TOKEN_KEY);

  async function request<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    let payload: BodyInit | undefined;
    if (form) payload = form; // the browser sets the multipart boundary itself
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    let res: Response;
    try {
      res = await doFetch(base + path, { method, headers, body: payload });
    } catch {
      throw new ApiError(0, "Cannot reach the server. Check your connection and try again.", "network");
    }
    let data: unknown = null;
    const text = await res.text();
    if (text) { try { data = JSON.parse(text); } catch { data = null; } }
    if (!res.ok) {
      const { message, code } = errorMessage(data, res.status);
      if (res.status === 401 && path !== "/auth/login") { clearToken(); opts.onUnauthorized?.(); }
      throw new ApiError(res.status, message, code);
    }
    return data as T;
  }

  const get = <T>(p: string) => request<T>("GET", p);
  return {
    getToken, setToken, clearToken, request,
    authConfig: () => get<AuthConfig>("/auth/config"),
    register: (email: string, password: string, org_name: string) =>
      request<{ user_id: number; org_id: number; role: string }>("POST", "/auth/register", { email, password, org_name }),
    async login(email: string, password: string) {
      const r = await request<{ access_token: string }>("POST", "/auth/login", { email, password });
      setToken(r.access_token);
    },
    me: () => get<Me>("/me"),
    status: () => get<Status>("/status"),
    dashboard: () => get<Dashboard>("/dashboard"),
    groups: () => get<Group[]>("/groups"),
    createGroup: (name: string) => request<{ group_id: number }>("POST", "/groups", { name }),
    users: () => get<UserItem[]>("/users"),
    createUser: (email: string, password: string, groups: string[], role: string) =>
      request<{ user_id: number }>("POST", "/users", { email, password, groups, role }),
    setUserGroups: (id: number, groups: string[]) =>
      request<{ id: number; groups: string[] }>("PUT", `/users/${id}/groups`, { groups }),
    documents: () => get<DocItem[]>("/documents"),
    uploadText: (title: string, text: string, groups: string[]) =>
      request<{ job_id: number }>("POST", "/documents", { title, text, groups }),
    uploadFile(file: File, title: string, groups: string[]) {
      const f = new FormData();
      f.append("file", file);
      f.append("title", title);
      f.append("groups", groups.join(","));
      return request<{ job_id: number }>("POST", "/documents/upload", undefined, f);
    },
    job: (id: number) => get<Job>(`/jobs/${id}`),
    query: (o: QueryOptions) => request<QueryResult>("POST", "/query", o),
    graph: () => get<GraphOverview>("/graph"),
    entity: (id: number) => get<Subgraph>(`/graph/entity/${id}`),
    audit: (limit = 100, action?: string) =>
      get<AuditEvent[]>(`/audit?limit=${limit}${action ? `&action=${encodeURIComponent(action)}` : ""}`),
  };
}
export type Client = ReturnType<typeof createClient>;
