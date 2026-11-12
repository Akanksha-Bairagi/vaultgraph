// Mirrors the FastAPI responses in vaultgraph/api.py + service.py.
export type Role = "admin" | "member";
export type DocStatus = "queued" | "processing" | "ready" | "failed";

export interface Me { id: number; email: string; role: Role; org_id: number; org_name: string; groups: string[] }
export interface DemoAccount { email: string; label: string; blurb: string }
export interface AuthConfig {
  registration_open: boolean; demo_mode: boolean; demo_accounts: DemoAccount[];
  demo_password: string | null; example_questions: string[];
}
export interface LlmStatus { provider: "groq" | "mock"; model: string; configured: boolean; healthy: boolean | null; detail: string }
export interface EmbedderStatus { requested: string; active: string; fallback: boolean; detail: string }
export interface Status {
  version: string; environment: string; llm: LlmStatus; embedder: EmbedderStatus;
  database: { engine: string; persistent: boolean | null; note: string }; demo_mode: boolean;
}
export interface DocItem {
  id: number; title: string; status: DocStatus; created_at: string; owner: string | null; groups: string[];
  chunks: number; quarantined_chunks: number; job_id: number | null; error: string | null; is_owner: boolean;
}
export interface Group { id: number; name: string; members: number | null }
export interface UserItem { id: number; email: string; role: Role; groups: string[] }
export interface Job { id: number; doc_id: number; status: string; error: string | null }
export interface Source { chunk_id: number; doc_id: number; doc_title: string; snippet: string; via: "search" | "graph" }
export interface GraphNode { id: number; name: string; type: string; depth?: number; degree?: number }
export interface GraphEdge {
  id: number; src: number; dst: number; rel: string; chunk_id: number; src_name: string; dst_name: string;
  doc_id: number; doc_title: string; evidence: string;
}
export interface Subgraph { nodes: GraphNode[]; edges: GraphEdge[] }
export interface GraphOverview extends Subgraph { truncated: boolean }
export interface QueryResult {
  answer: string; citations: number[]; sources: Source[]; provider: string; model: string; facts: string[];
  subgraph: Subgraph; violations: string[]; quarantined: number; latency_ms: number;
}
export interface Dashboard {
  documents: { total: number; ready: number; queued: number; processing: number; failed: number };
  groups: number; queries: { total: number; last_7_days: number };
  recent_queries: { ts: string; question: string; sources: number; flagged: boolean }[];
  users: number | null; recent_activity: { ts: string; actor: string | null; action: string }[];
}
export interface AuditEvent { id: number; ts: string; user_id: number | null; actor: string | null; action: string; detail: Record<string, unknown> }
export interface QueryOptions { question: string; top_k?: number; hops?: number; use_graph?: boolean }
