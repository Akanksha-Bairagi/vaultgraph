import test from "node:test";
import assert from "node:assert/strict";
import { actionLabel, describeAudit, initials, relativeTime } from "./format.ts";

const now = Date.parse("2026-11-07T12:00:00Z");
test("relativeTime buckets", () => {
  assert.equal(relativeTime("2026-11-07T11:59:50Z", now), "just now");
  assert.equal(relativeTime("2026-11-07T11:30:00Z", now), "30 min ago");
  assert.equal(relativeTime("2026-11-07T09:00:00Z", now), "3 h ago");
  assert.equal(relativeTime("2026-11-04T12:00:00Z", now), "3 d ago");
  assert.equal(relativeTime("garbage", now), "");
});
test("initials", () => {
  assert.equal(initials("ava.stone@x.test"), "AS");
  assert.equal(initials("hr@x.test"), "H");
});
test("audit descriptions never throw on odd details", () => {
  assert.match(describeAudit("query", { question: "Who?", chunk_ids: [1, 2], violations: ["foreign_url"] }), /2 sources · output blocked/);
  assert.equal(describeAudit("set_user_groups", { user: "a@b.test", groups: ["eng"] }), "a@b.test → eng");
  assert.equal(describeAudit("query", {}), "“” · 0 sources");
  assert.equal(describeAudit("mystery", {}), "");
  assert.equal(actionLabel("ingest_done"), "Document processed");
  assert.equal(actionLabel("brand_new_action"), "brand new action");
});
