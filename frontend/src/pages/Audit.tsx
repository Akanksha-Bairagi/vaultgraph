import { Fragment, useState } from "react";
import { ChevronRight, RefreshCw, ScrollText, ShieldAlert } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { actionLabel, describeAudit, fullDate } from "../lib/format.ts";
import { Badge, Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui.tsx";

const FILTERS = ["", "query", "query_error", "login", "login_failed", "submit_document", "ingest_done", "create_user", "set_user_groups", "create_group", "graph_view"];
const tone = (a: string) => (a === "login_failed" || a === "query_error" ? "bad" : a === "query" ? "info" : a.startsWith("set_") || a.startsWith("create_") ? "warn" : "neutral");

export function Audit() {
  const { user } = useAuth();
  const [action, setAction] = useState("");
  const [limit, setLimit] = useState(100);
  const [open, setOpen] = useState<number | null>(null);
  const log = useAsync(() => api.audit(limit, action || undefined), [action, limit]);
  if (user?.role !== "admin") return <Card><Empty icon={<ShieldAlert size={26} />} title="Administrator access required" hint="Only workspace administrators can read the audit log." /></Card>;

  return (
    <>
      <PageHeader title="Audit log" subtitle="Who asked what, which passages were used, and which defenses fired."
        actions={<>
          <select value={action} onChange={(e) => setAction(e.target.value)} aria-label="Filter by action">{FILTERS.map((f) => <option key={f} value={f}>{f ? actionLabel(f) : "All actions"}</option>)}</select>
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} aria-label="Rows">{[50, 100, 250, 500].map((n) => <option key={n} value={n}>{n} rows</option>)}</select>
          <button className="btn" onClick={log.reload}><RefreshCw size={15} /> Refresh</button>
        </>} />
      <Card>
        {log.error && <ErrorNote message={log.error} onRetry={log.reload} />}
        {log.loading && !log.data && <Spinner label="Loading events…" />}
        {log.data && log.data.length === 0 && <Empty icon={<ScrollText size={24} />} title="No events match" />}
        {log.data && log.data.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th /><th>Time</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead>
              <tbody>
                {log.data.map((e) => (
                  <Fragment key={e.id}>
                    <tr className="clickable" onClick={() => setOpen(open === e.id ? null : e.id)}>
                      <td><ChevronRight size={14} className={open === e.id ? "rot" : ""} aria-hidden /></td>
                      <td className="nowrap">{fullDate(e.ts)}</td>
                      <td>{e.actor ?? <span className="muted">system / anonymous</span>}</td>
                      <td><Badge tone={tone(e.action)}>{actionLabel(e.action)}</Badge></td>
                      <td className="clamp-cell">{describeAudit(e.action, e.detail)}</td>
                    </tr>
                    {open === e.id && <tr className="detail-row"><td /><td colSpan={4}><pre>{JSON.stringify(e.detail, null, 2)}</pre></td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
