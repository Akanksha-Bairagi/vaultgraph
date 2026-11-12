export type Part = { type: "text"; value: string } | { type: "cite"; id: number };

/** Splits an answer into text and [c12]-style citation markers so the UI can render clickable chips. */
export function splitCitations(answer: string): Part[] {
  const parts: Part[] = [];
  const re = /\[c(\d+)\]/g;
  let last = 0;
  for (let m = re.exec(answer); m; m = re.exec(answer)) {
    if (m.index > last) parts.push({ type: "text", value: answer.slice(last, m.index) });
    parts.push({ type: "cite", id: Number(m[1]) });
    last = m.index + m[0].length;
  }
  if (last < answer.length) parts.push({ type: "text", value: answer.slice(last) });
  return parts;
}

/** Citation numbers in order of first appearance, de-duplicated. */
export function citedIds(answer: string): number[] {
  const seen: number[] = [];
  for (const p of splitCitations(answer)) if (p.type === "cite" && !seen.includes(p.id)) seen.push(p.id);
  return seen;
}
