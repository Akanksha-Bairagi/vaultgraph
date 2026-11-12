export interface LNode { id: number }
export interface LEdge { src: number; dst: number }
export interface Pos { x: number; y: number }

/** Small deterministic force-directed layout (repulsion + springs + gravity), O(n^2 * iterations).
 *  Fine for the <= 300 nodes the API returns. Returns coordinates inside [pad, width-pad] x [pad, height-pad]. */
export function layout(nodes: LNode[], edges: LEdge[], width = 900, height = 600, iterations = 320, pad = 40): Map<number, Pos> {
  const out = new Map<number, Pos>();
  const n = nodes.length;
  if (n === 0) return out;
  if (n === 1) { out.set(nodes[0].id, { x: width / 2, y: height / 2 }); return out; }
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  const x = new Float64Array(n), y = new Float64Array(n), vx = new Float64Array(n), vy = new Float64Array(n);
  for (let i = 0; i < n; i++) { // circle start with a tiny deterministic jitter (no Math.random: stable between renders)
    const a = (2 * Math.PI * i) / n;
    x[i] = width / 2 + Math.cos(a) * width * 0.3 + ((i * 7919) % 13) - 6;
    y[i] = height / 2 + Math.sin(a) * height * 0.3 + ((i * 104729) % 11) - 5;
  }
  const links = edges.map((e) => [idx.get(e.src), idx.get(e.dst)] as const).filter((l): l is [number, number] => l[0] !== undefined && l[1] !== undefined && l[0] !== l[1]);
  const k = Math.sqrt((width * height) / n) * 0.6; // ideal edge length
  for (let it = 0; it < iterations; it++) {
    const t = 1 - it / iterations; // cooling
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = x[i] - x[j], dy = y[i] - y[j];
        let d2 = dx * dx + dy * dy;
        if (d2 < 0.01) { dx = 0.1 * (i - j); dy = 0.1; d2 = dx * dx + dy * dy; }
        const d = Math.sqrt(d2), f = (k * k) / d / d; // repulsion ~ k^2/d
        vx[i] += dx * f; vy[i] += dy * f; vx[j] -= dx * f; vy[j] -= dy * f;
      }
    }
    for (const [a, b] of links) {
      const dx = x[b] - x[a], dy = y[b] - y[a], d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = (d - k) / d * 0.08; // spring toward rest length k
      vx[a] += dx * f; vy[a] += dy * f; vx[b] -= dx * f; vy[b] -= dy * f;
    }
    for (let i = 0; i < n; i++) {
      vx[i] += (width / 2 - x[i]) * 0.01; vy[i] += (height / 2 - y[i]) * 0.01; // gravity
      const sp = Math.hypot(vx[i], vy[i]), cap = 30 * t + 1;
      if (sp > cap) { vx[i] *= cap / sp; vy[i] *= cap / sp; }
      x[i] += vx[i]; y[i] += vy[i]; vx[i] *= 0.6; vy[i] *= 0.6;
    }
  }
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < n; i++) { minX = Math.min(minX, x[i]); maxX = Math.max(maxX, x[i]); minY = Math.min(minY, y[i]); maxY = Math.max(maxY, y[i]); }
  const sx = maxX - minX || 1, sy = maxY - minY || 1;
  nodes.forEach((nd, i) => out.set(nd.id, { x: pad + ((x[i] - minX) / sx) * (width - 2 * pad), y: pad + ((y[i] - minY) / sy) * (height - 2 * pad) }));
  return out;
}
