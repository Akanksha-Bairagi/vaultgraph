import test from "node:test";
import assert from "node:assert/strict";
import { layout } from "./forceLayout.ts";

const dist = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.hypot(a.x - b.x, a.y - b.y);

test("empty and single-node graphs", () => {
  assert.equal(layout([], []).size, 0);
  const p = layout([{ id: 1 }], []).get(1)!;
  assert.deepEqual(p, { x: 450, y: 300 });
});

test("positions are finite, inside bounds and deterministic", () => {
  const nodes = Array.from({ length: 40 }, (_, i) => ({ id: i + 1 }));
  const edges = nodes.slice(1).map((n, i) => ({ src: nodes[i].id, dst: n.id }));
  const a = layout(nodes, edges, 800, 500), b = layout(nodes, edges, 800, 500);
  for (const nd of nodes) {
    const p = a.get(nd.id)!;
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
    assert.ok(p.x >= 40 - 1e-6 && p.x <= 760 + 1e-6 && p.y >= 40 - 1e-6 && p.y <= 460 + 1e-6);
    assert.deepEqual(p, b.get(nd.id));
  }
});

test("connected nodes end up closer than unconnected ones on average", () => {
  const nodes = Array.from({ length: 12 }, (_, i) => ({ id: i }));
  const edges = [[0, 1], [1, 2], [2, 0], [3, 4], [4, 5], [5, 3], [6, 7], [7, 8], [8, 6], [9, 10], [10, 11], [11, 9]].map(([src, dst]) => ({ src, dst }));
  const pos = layout(nodes, edges);
  let near = 0, nearN = 0, far = 0, farN = 0;
  const linked = new Set(edges.map((e) => `${Math.min(e.src, e.dst)}-${Math.max(e.src, e.dst)}`));
  for (let i = 0; i < 12; i++) for (let j = i + 1; j < 12; j++) {
    const d = dist(pos.get(i)!, pos.get(j)!);
    if (linked.has(`${i}-${j}`)) { near += d; nearN++; } else { far += d; farN++; }
  }
  assert.ok(near / nearN < far / farN, `linked ${near / nearN} should be < unlinked ${far / farN}`);
});

test("edges to unknown nodes are ignored", () => {
  const p = layout([{ id: 1 }, { id: 2 }], [{ src: 1, dst: 99 }]);
  assert.equal(p.size, 2);
});
