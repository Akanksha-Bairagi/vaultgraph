import { useEffect, useRef, useState, type FormEvent } from "react";
import { AlertTriangle, ChevronDown, Link2, Loader2, Network, SendHorizonal, ShieldCheck, Sparkles } from "lucide-react";
import { messageOf, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { splitCitations } from "../lib/citations.ts";
import { REL_LABEL } from "../lib/graphStyle.ts";
import type { QueryResult } from "../types.ts";
import { Badge, Empty, ErrorNote } from "../components/ui.tsx";

interface Turn { id: number; question: string; result?: QueryResult; error?: string; pending: boolean }

export function Ask() {
  const cfg = useAsync(() => api.authConfig(), []);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState(() => { const p = sessionStorage.getItem("vg_prefill"); sessionStorage.removeItem("vg_prefill"); return p ?? ""; });
  const [useGraph, setUseGraph] = useState(true);
  const [hops, setHops] = useState(3);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, question: text, pending: true }]);
    setQ(""); setBusy(true);
    try {
      const result = await api.query({ question: text, use_graph: useGraph, hops });
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, result, pending: false } : x)));
    } catch (err) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error: messageOf(err), pending: false } : x)));
    } finally { setBusy(false); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(q); };
  const examples = cfg.data?.example_questions ?? [];

  return (
    <div className="chat">
      <div className="chat-scroll">
        {turns.length === 0 && (
          <Empty icon={<Sparkles size={28} />} title="Ask about your documents" hint="Answers cite the exact passages used, and only draw on documents you’re allowed to see.">
            {examples.length > 0 && <div className="examples">{examples.map((e) => <button key={e} className="example" onClick={() => void ask(e)}>{e}</button>)}</div>}
          </Empty>
        )}
        {turns.map((t) => <TurnView key={t.id} t={t} />)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <div className="composer-opts">
          <label className="toggle"><input type="checkbox" checked={useGraph} onChange={(e) => setUseGraph(e.target.checked)} /> Use knowledge graph</label>
          <label className={`hops ${useGraph ? "" : "off"}`}>Hops <input type="range" min={1} max={4} value={hops} disabled={!useGraph} onChange={(e) => setHops(Number(e.target.value))} /> <b>{hops}</b></label>
        </div>
        <div className="composer-row">
          <textarea value={q} rows={1} maxLength={1000} placeholder="Ask a question… (Enter to send, Shift+Enter for a new line)" aria-label="Your question"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void ask(q); } }} />
          <button className="btn btn-primary" disabled={busy || !q.trim()} aria-label="Send">{busy ? <Loader2 size={16} className="spin" /> : <SendHorizonal size={16} />}</button>
        </div>
      </form>
    </div>
  );
}

function TurnView({ t }: { t: Turn }) {
  return (
    <div className="turn">
      <div className="bubble-user">{t.question}</div>
      {t.pending && <div className="bubble-ai skeleton" aria-busy="true"><span className="muted"><Loader2 size={14} className="spin" /> Searching documents and walking the graph…</span><i /><i /><i /></div>}
      {t.error && <ErrorNote message={t.error} />}
      {t.result && <Answer r={t.result} />}
    </div>
  );
}

export function Answer({ r }: { r: QueryResult }) {
  const [hl, setHl] = useState<number | null>(null);
  const [showFacts, setShowFacts] = useState(false);
  const empty = !r.answer.trim() || r.sources.length === 0;
  const sourceIds = new Set(r.sources.map((s) => s.chunk_id));
  const jump = (id: number) => { setHl(id); document.getElementById(`src-${id}-${r.latency_ms}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }); };

  return (
    <div className="bubble-ai">
      {r.violations.length > 0 && (
        <div className="note note-warn"><ShieldCheck size={16} />The output validator {r.violations.includes("canary_leak") || r.violations.includes("foreign_url") || r.violations.includes("markdown_image") ? "blocked this answer" : "adjusted this answer"} ({r.violations.join(", ").replace(/_/g, " ")}).</div>
      )}
      <p className="answer-text">
        {splitCitations(r.answer).map((p, i) => p.type === "text" ? <span key={i}>{p.value}</span> :
          sourceIds.has(p.id)
            ? <button key={i} className="cite" onClick={() => jump(p.id)} title="Show source">{p.id}</button>
            : <span key={i} className="cite cite-bad" title="Not a source of this answer">?</span>)}
      </p>
      {empty && <p className="muted small">No supporting passages were found in documents you can access.</p>}
      {r.quarantined > 0 && <div className="note note-warn small"><AlertTriangle size={14} />{r.quarantined} passage(s) were excluded because the injection scanner flagged them.</div>}

      {r.sources.length > 0 && (
        <div className="sources">
          <h4><Link2 size={14} /> Sources ({r.sources.length})</h4>
          {r.sources.map((s) => (
            <article key={s.chunk_id} id={`src-${s.chunk_id}-${r.latency_ms}`} className={`source ${hl === s.chunk_id ? "hl" : ""}`}>
              <header><strong>{s.doc_title}</strong><span className="chip">c{s.chunk_id}</span>{s.via === "graph" && <Badge tone="info"><Network size={11} /> via graph</Badge>}</header>
              <p>{s.snippet}</p>
            </article>
          ))}
        </div>
      )}

      {r.facts.length > 0 && (
        <div className="facts">
          <button className="link" onClick={() => setShowFacts((v) => !v)} aria-expanded={showFacts}><ChevronDown size={14} className={showFacts ? "rot" : ""} /> Graph relationships used ({r.facts.length})</button>
          {showFacts && <ul>{r.facts.map((f, i) => <li key={i}>{f.replace(/-\[([A-Z_]+)\]->/, (_m, rel: string) => `— ${REL_LABEL(rel)} →`)}</li>)}</ul>}
        </div>
      )}
      <footer className="answer-meta">{r.provider === "groq" ? `Groq · ${r.model}` : "Offline mock LLM"} · {r.latency_ms} ms · {r.subgraph.nodes.length} entities</footer>
    </div>
  );
}
