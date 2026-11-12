import { useEffect, useRef, useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, ClipboardPaste, FileText, Loader2, RefreshCw, ShieldAlert, Upload } from "lucide-react";
import { useAuth } from "../auth.tsx";
import { messageOf, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { fullDate } from "../lib/format.ts";
import type { DocItem } from "../types.ts";
import { Badge, Card, Empty, ErrorNote, GroupPicker, PageHeader, Spinner } from "../components/ui.tsx";

const MAX_MB = 2;

export function Documents() {
  const { user } = useAuth();
  const docs = useAsync(() => api.documents(), []);
  const groups = useAsync(() => api.groups(), []);
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [sel, setSel] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const names = (groups.data ?? []).map((g) => g.name);

  // Poll while anything is still being processed.
  const pending = (docs.data ?? []).some((d) => d.status === "queued" || d.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(docs.reload, 1500);
    return () => clearInterval(t);
  }, [pending, docs.reload]);

  function pick(f: File | null) {
    setError(null);
    if (f && f.size > MAX_MB * 1024 * 1024) { setError(`That file is larger than ${MAX_MB} MB.`); return; }
    if (f && !/\.(pdf|txt|md)$/i.test(f.name)) { setError("Only .pdf, .txt and .md files are supported."); return; }
    setFile(f);
    if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setNotice(null);
    if (mode === "file" && !file) { setError("Choose a file first."); return; }
    if (mode === "text" && (!title.trim() || !text.trim())) { setError("Enter a title and some text."); return; }
    setBusy(true);
    try {
      if (mode === "file" && file) await api.uploadFile(file, title.trim(), sel);
      else await api.uploadText(title.trim(), text, sel);
      setNotice(sel.length ? `Uploaded. It will be searchable by: ${sel.join(", ")}.` : "Uploaded. With no groups selected, only administrators can see it.");
      setFile(null); setTitle(""); setText(""); setSel([]);
      if (fileRef.current) fileRef.current.value = "";
      docs.reload();
    } catch (err) { setError(messageOf(err)); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Documents" subtitle="Upload files and decide which groups can find them. Access is default-deny."
        actions={<button className="btn" onClick={docs.reload}><RefreshCw size={15} /> Refresh</button>} />
      <div className="two-col wide-left">
        <Card title="Add a document">
          <div className="tabs small-tabs" role="tablist">
            <button role="tab" aria-selected={mode === "file"} className={mode === "file" ? "on" : ""} onClick={() => setMode("file")}><Upload size={14} /> Upload file</button>
            <button role="tab" aria-selected={mode === "text"} className={mode === "text" ? "on" : ""} onClick={() => setMode("text")}><ClipboardPaste size={14} /> Paste text</button>
          </div>
          <form className="form" onSubmit={submit}>
            {mode === "file" ? (
              <label className={`dropzone ${file ? "has-file" : ""}`}
                onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0] ?? null); }}>
                <Upload size={22} aria-hidden />
                <strong>{file ? file.name : "Choose a PDF, TXT or Markdown file"}</strong>
                <span className="muted small">{file ? `${(file.size / 1024).toFixed(0)} KB` : `or drag it here · up to ${MAX_MB} MB`}</span>
                <input ref={fileRef} type="file" accept=".pdf,.txt,.md" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
              </label>
            ) : (
              <label>Text<textarea rows={6} value={text} maxLength={200000} onChange={(e) => setText(e.target.value)} placeholder="Paste document text…" /></label>
            )}
            <label>Title<input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Orion architecture notes" /></label>
            <div>
              <span className="label">Who can find this document?</span>
              <GroupPicker groups={names} selected={sel} onChange={setSel} />
              {user?.role !== "admin" && <p className="muted small">You can only share with groups you belong to.</p>}
            </div>
            {error && <ErrorNote message={error} />}
            {notice && <div className="note note-ok"><CheckCircle2 size={16} />{notice}</div>}
            <button className="btn btn-primary" disabled={busy}>{busy ? <Loader2 size={16} className="spin" /> : <Upload size={16} />} Upload &amp; index</button>
          </form>
        </Card>

        <Card title="Documents you can access">
          {docs.error && <ErrorNote message={docs.error} onRetry={docs.reload} />}
          {docs.loading && !docs.data && <Spinner label="Loading documents…" />}
          {docs.data && docs.data.length === 0 && <Empty icon={<FileText size={24} />} title="No documents yet" hint="Upload your first document to start building the knowledge graph." />}
          <ul className="doc-list">{docs.data?.map((d) => <DocRow key={d.id} d={d} />)}</ul>
        </Card>
      </div>
    </>
  );
}

function DocRow({ d }: { d: DocItem }) {
  return (
    <li className="doc-row">
      <FileText size={20} className="c-muted" aria-hidden />
      <div className="doc-main">
        <strong>{d.title}</strong>
        <div className="chips">{d.groups.length ? d.groups.map((g) => <span key={g} className="chip">{g}</span>) : <span className="chip chip-warn">admins only</span>}</div>
        <span className="muted small">{fullDate(d.created_at)}{d.owner ? ` · ${d.owner}` : ""} · {d.chunks} chunk{d.chunks === 1 ? "" : "s"}</span>
        {d.quarantined_chunks > 0 && <span className="small c-warn inline-icon"><ShieldAlert size={14} />{d.quarantined_chunks} chunk(s) quarantined by the injection scanner. They are excluded from answers and the graph.</span>}
        {d.status === "failed" && <span className="small c-bad inline-icon"><AlertTriangle size={14} />Processing failed{d.error ? ` (${d.error})` : ""}. Try uploading it again.</span>}
      </div>
      <StatusBadge s={d.status} />
    </li>
  );
}

function StatusBadge({ s }: { s: DocItem["status"] }) {
  if (s === "ready") return <Badge tone="ok">Ready</Badge>;
  if (s === "failed") return <Badge tone="bad">Failed</Badge>;
  return <Badge tone="info"><Loader2 size={12} className="spin" /> {s === "queued" ? "Queued" : "Processing"}</Badge>;
}
