import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Clock, Database, FileText, MessageSquareText, Network, Users } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { navigate, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { actionLabel, relativeTime } from "../lib/format.ts";
import { Badge, Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui.tsx";

export function Dashboard() {
  const { user } = useAuth();
  const dash = useAsync(() => api.dashboard(), []);
  const status = useAsync(() => api.status(), []);
  const d = dash.data;
  const s = status.data;

  return (
    <>
      <PageHeader title={`Welcome back${user ? `, ${user.email.split("@")[0]}` : ""}`} subtitle={`${user?.org_name ?? ""} · ${user?.groups.length ? user.groups.join(", ") : user?.role === "admin" ? "administrator" : "no groups"}`}
        actions={<button className="btn btn-primary" onClick={() => navigate("/ask")}><MessageSquareText size={16} /> Ask a question</button>} />
      {dash.error && <ErrorNote message={dash.error} onRetry={dash.reload} />}
      {dash.loading && !d && <Spinner label="Loading overview…" />}
      {d && (
        <div className="stat-grid">
          <Stat icon={<FileText size={18} />} label="Documents you can access" value={d.documents.total}
            foot={`${d.documents.ready} ready${d.documents.processing + d.documents.queued ? ` · ${d.documents.processing + d.documents.queued} processing` : ""}${d.documents.failed ? ` · ${d.documents.failed} failed` : ""}`} onClick={() => navigate("/documents")} />
          <Stat icon={<MessageSquareText size={18} />} label="Your questions" value={d.queries.total} foot={`${d.queries.last_7_days} in the last 7 days`} onClick={() => navigate("/ask")} />
          <Stat icon={<Network size={18} />} label="Your groups" value={d.groups} foot="Membership decides what you can search" />
          {d.users !== null && <Stat icon={<Users size={18} />} label="People in workspace" value={d.users} foot="Manage under People & groups" onClick={() => navigate("/people")} />}
        </div>
      )}

      <div className="two-col">
        <Card title="Recent questions" action={<button className="link" onClick={() => navigate("/ask")}>Ask another</button>}>
          {d && d.recent_queries.length === 0 && <Empty icon={<MessageSquareText size={22} />} title="No questions yet" hint="Ask something about your documents to see it here." />}
          <ul className="list">
            {d?.recent_queries.map((q, i) => (
              <li key={i} className="list-row">
                <div><strong className="clamp">{q.question}</strong><span className="muted small">{relativeTime(q.ts)} · {q.sources} source{q.sources === 1 ? "" : "s"}</span></div>
                {q.flagged && <Badge tone="warn">output edited</Badge>}
                <button className="link" onClick={() => { sessionStorage.setItem("vg_prefill", q.question); navigate("/ask"); }}>Ask again</button>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="System status" action={<button className="link" onClick={status.reload}>Refresh</button>}>
          {status.loading && !s && <Spinner />}
          {status.error && <ErrorNote message={status.error} />}
          {s && (
            <ul className="status-list">
              <li>{s.llm.healthy === false ? <AlertTriangle size={16} className="c-bad" /> : <CheckCircle2 size={16} className={s.llm.provider === "mock" ? "c-warn" : "c-ok"} />}
                <div><strong>Language model: {s.llm.provider === "groq" ? "Groq" : "Offline mock"}</strong><span className="muted small">{s.llm.model} — {s.llm.detail}</span></div></li>
              <li><CheckCircle2 size={16} className={s.embedder.fallback ? "c-warn" : "c-ok"} />
                <div><strong>Embeddings: {s.embedder.active}</strong><span className="muted small">{s.embedder.detail}</span></div></li>
              <li><Database size={16} className="c-warn" />
                <div><strong>Storage: {s.database.engine}</strong><span className="muted small">{s.database.note}</span></div></li>
              <li><Clock size={16} className="c-muted" /><div><strong>Version {s.version}</strong><span className="muted small">Environment: {s.environment}{s.demo_mode ? " · public demo mode" : ""}</span></div></li>
            </ul>
          )}
        </Card>
      </div>

      {user?.role === "admin" && d && (
        <Card title="Recent workspace activity" action={<button className="link" onClick={() => navigate("/audit")}>Open audit log</button>}>
          {d.recent_activity.length === 0 ? <p className="muted">No activity yet.</p> : (
            <ul className="list">
              {d.recent_activity.map((a, i) => (
                <li key={i} className="list-row"><div><strong>{actionLabel(a.action)}</strong><span className="muted small">{a.actor ?? "system"}</span></div><span className="muted small">{relativeTime(a.ts)}</span></li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}

function Stat({ icon, label, value, foot, onClick }: { icon: ReactNode; label: string; value: number; foot: string; onClick?: () => void }) {
  const inner = (<><div className="stat-top">{icon}<span>{label}</span></div><div className="stat-value">{value}</div><div className="muted small">{foot}</div></>);
  return onClick ? <button className="stat stat-click" onClick={onClick}>{inner}</button> : <div className="stat">{inner}</div>;
}
