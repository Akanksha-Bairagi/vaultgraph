import test from "node:test";
import assert from "node:assert/strict";
import { citedIds, splitCitations } from "./citations.ts";

test("splits text and citation markers in order", () => {
  assert.deepEqual(splitCitations("A is B [c12]. C [c3]."), [
    { type: "text", value: "A is B " }, { type: "cite", id: 12 }, { type: "text", value: ". C " }, { type: "cite", id: 3 }, { type: "text", value: "." },
  ]);
});
test("no citations -> single text part; empty -> none", () => {
  assert.deepEqual(splitCitations("plain"), [{ type: "text", value: "plain" }]);
  assert.deepEqual(splitCitations(""), []);
});
test("citedIds de-duplicates and keeps first-seen order", () => {
  assert.deepEqual(citedIds("x [c2] y [c1] z [c2]"), [2, 1]);
});
test("lookalikes are not treated as citations", () => {
  assert.deepEqual(citedIds("[c] [cx1] [c 5] (c7)"), []);
});
