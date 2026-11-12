import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent, type WheelEvent as RWheelEvent } from "react";
import { FileText, Maximize2, Network, Search, ZoomIn, ZoomOut } from "lucide-react";
import { messageOf, useAsync } from "../hooks.ts";
import { api } from "../lib/client.ts";
import { layout } from "../lib/forceLayout.ts";
import { REL_LABEL, TYPE_COLORS, colorFor } from "../lib/graphStyle.ts";
import type { GraphEdge, GraphNode, GraphOverview, Subgraph } from "../types.ts";
import { Card, Empty, ErrorNote, PageHeader, Spinner } from "../components/ui.tsx";

const W = 900, H = 600;

export function Graph() {
  const g = useAsync(() => api.graph(), []);
  return (
    <>
      <PageHeader title="Knowledge graph" subtitle="Entities and relationships extracted from documents you can access. Every edge links back to its source passage." />
      {g.error && <ErrorNote message={g.error} onRetry={g.reload} />}
      {g.loading && !g.data && <Spinner label="Building graph…" />}
      {g.data && g.data.nodes.length === 0 && <Card><Empty icon={<Network size={26} />} title="No entities yet" hint="Upload documents with statements like “Project Orion depends on Atlas Database.” to populate the graph." /></Card>}
      {g.data && g.data.nodes.length > 0 && <GraphExplorer data={g.data} />}
    </>
  );
}

/** Interactive view (layout, pan/zoom, search, selection). Separate from data loading so it can be rendered in tests. */
export function GraphExplorer({ data }: { data: GraphOverview }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [neighbors, setNeighbors] = useState<Subgraph | null>(null);
  const [nerr, setNerr] = useState<string | null>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const nodes = data.nodes;
  const edges = data.edges;
  const pos = useMemo(() => layout(nodes, edges, W, H), [nodes, edges]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  useEffect(() => { // explore: ask the API for the selected entity's visible neighbourhood (ACL-filtered server-side)
    setNeighbors(null); setNerr(null);
    if (selected === null) return;
    let alive = true;
    api.entity(selected).then((s) => { if (alive) setNeighbors(s); }, (e) => { if (alive) setNerr(messageOf(e)); });
    return () => { alive = false; };
  }, [selected]);

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => new Set(q ? nodes.filter((n) => n.name.toLowerCase().includes(q)).map((n) => n.id) : []), [nodes, q]);
  const focus = hover ?? selected;
  const near = useMemo(() => {
    const s = new Set<number>();
    if (focus !== null) { s.add(focus); edges.forEach((e) => { if (e.src === focus) s.add(e.dst); if (e.dst === focus) s.add(e.src); }); }
    return s;
  }, [focus, edges]);

  const sel: GraphNode | undefined = selected !== null ? byId.get(selected) : undefined;
  const selEdges: GraphEdge[] = (neighbors?.edges ?? edges).filter((e) => e.src === selected || e.dst === selected);
  const types = useMemo(() => [...new Set(nodes.map((n) => n.type))], [nodes]);

  function onWheel(e: RWheelEvent<SVGSVGElement>) { setZoom((z) => Math.min(3, Math.max(0.4, z * (e.deltaY < 0 ? 1.1 : 0.9)))); }
  function onDown(e: RPointerEvent<SVGSVGElement>) { drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }; (e.currentTarget as Element).setPointerCapture(e.pointerId); }
  function onMove(e: RPointerEvent<SVGSVGElement>) {
    const d = drag.current, r = svgRef.current?.getBoundingClientRect();
    if (!d || !r) return;
    setPan({ x: d.px + ((e.clientX - d.x) * W) / r.width, y: d.py + ((e.clientY - d.y) * H) / r.height });
  }
  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  return (
        <div className="graph-layout">
          <Card className="graph-card">
            <div className="graph-tools">
              <label className="search"><Search size={15} aria-hidden /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find an entity…" aria-label="Find an entity" /></label>
              <div className="zoom">
                <button className="icon-btn" onClick={() => setZoom((z) => Math.min(3, z * 1.2))} aria-label="Zoom in"><ZoomIn size={16} /></button>
                <button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.4, z / 1.2))} aria-label="Zoom out"><ZoomOut size={16} /></button>
                <button className="icon-btn" onClick={reset} aria-label="Reset view"><Maximize2 size={16} /></button>
              </div>
            </div>
            <svg ref={svgRef} className="graph-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Knowledge graph with ${nodes.length} entities and ${edges.length} relationships`}
              onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }} onClick={() => setSelected(null)}>
              <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z" fill="#9aa8a3" /></marker></defs>
              <g transform={`translate(${W / 2 + pan.x} ${H / 2 + pan.y}) scale(${zoom}) translate(${-W / 2} ${-H / 2})`}>
                {edges.map((e) => {
                  const a = pos.get(e.src), b = pos.get(e.dst);
                  if (!a || !b) return null;
                  const dim = focus !== null && !(near.has(e.src) && near.has(e.dst) && (e.src === focus || e.dst === focus));
                  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
                  const x2 = b.x - (dx / len) * 16, y2 = b.y - (dy / len) * 16;
                  return (
                    <g key={e.id} className={dim ? "edge dim" : "edge"}>
                      <line x1={a.x} y1={a.y} x2={x2} y2={y2} markerEnd="url(#arrow)" />
                      {!dim && <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} textAnchor="middle">{REL_LABEL(e.rel)}</text>}
                    </g>
                  );
                })}
                {nodes.map((n) => {
                  const p = pos.get(n.id);
                  if (!p) return null;
                  const dim = (focus !== null && !near.has(n.id)) || (q !== "" && !matches.has(n.id));
                  return (
                    <g key={n.id} className={`node ${dim ? "dim" : ""} ${selected === n.id ? "sel" : ""}`} transform={`translate(${p.x} ${p.y})`} tabIndex={0} role="button" aria-label={`${n.name} (${n.type})`}
                      onPointerDown={(ev) => ev.stopPropagation()} onClick={(ev) => { ev.stopPropagation(); setSelected(n.id); }}
                      onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setSelected(n.id); } }}
                      onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
                      <circle r={10 + Math.min(8, (n.degree ?? 0) * 1.5)} fill={colorFor(n.type)} />
                      <text y={-16 - Math.min(8, (n.degree ?? 0) * 1.5) + 6} textAnchor="middle">{n.name}</text>
                    </g>
                  );
                })}
              </g>
            </svg>
            <div className="legend">{types.map((t) => <span key={t}><i style={{ background: TYPE_COLORS[t] ?? TYPE_COLORS.entity }} />{t}</span>)}
              <span className="muted small">{nodes.length} entities · {edges.length} relationships{data.truncated ? " (largest shown)" : ""}</span></div>
          </Card>

          <Card title={sel ? sel.name : "Details"} className="graph-side">
            {!sel && <p className="muted">Select an entity to see its relationships and the documents they come from. Drag to pan, scroll to zoom.</p>}
            {sel && (
              <>
                <p className="muted small">Type: {sel.type} · {selEdges.length} relationship{selEdges.length === 1 ? "" : "s"} visible to you</p>
                {nerr && <ErrorNote message={nerr} />}
                {!neighbors && !nerr && <Spinner />}
                <ul className="rel-list">
                  {selEdges.map((e) => (
                    <li key={e.id}>
                      <div className="rel"><button className="link" onClick={() => setSelected(e.src === sel.id ? e.dst : e.src)}>{e.src === sel.id ? e.dst_name : e.src_name}</button>
                        <span className="muted small">{e.src === sel.id ? `${REL_LABEL(e.rel)} →` : `← ${REL_LABEL(e.rel)}`}</span></div>
                      <div className="prov"><FileText size={13} aria-hidden /><b>{e.doc_title}</b><p>{e.evidence}</p></div>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        </div>
  );
}
