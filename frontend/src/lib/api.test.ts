import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, createClient, errorMessage } from "./api.ts";

class MemStore {
  m = new Map<string, string>();
  getItem(k: string) { return this.m.get(k) ?? null; }
  setItem(k: string, v: string) { this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
}
type Call = { url: string; init: RequestInit };
function mockFetch(responses: Array<{ status?: number; body?: unknown } | Error>) {
  const calls: Call[] = [];
  const fetchImpl = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const r = responses.shift() ?? { status: 200, body: {} };
    if (r instanceof Error) throw r;
    const status = r.status ?? 200;
    return new Response(r.body === undefined ? "" : JSON.stringify(r.body), { status });
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

test("login stores the token and later requests send it as a Bearer header", async () => {
  const store = new MemStore();
  const { fetchImpl, calls } = mockFetch([{ body: { access_token: "tok123" } }, { body: { id: 1, email: "a@b.test" } }]);
  const api = createClient({ fetchImpl, storage: store });
  await api.login("a@b.test", "pw");
  assert.equal(store.getItem("vg_token"), "tok123");
  await api.me();
  assert.equal((calls[1].init.headers as Record<string, string>)["Authorization"], "Bearer tok123");
  assert.equal(calls[1].url, "/me");
});

test("401 on a normal call clears the token and fires onUnauthorized; failed login does not", async () => {
  const store = new MemStore();
  store.setItem("vg_token", "old");
  let fired = 0;
  const { fetchImpl } = mockFetch([{ status: 401, body: { detail: "invalid or expired token" } }, { status: 401, body: { detail: "invalid credentials" } }]);
  const api = createClient({ fetchImpl, storage: store, onUnauthorized: () => { fired++; } });
  await assert.rejects(api.me(), (e: unknown) => e instanceof ApiError && e.status === 401 && e.message === "invalid or expired token");
  assert.equal(store.getItem("vg_token"), null);
  assert.equal(fired, 1);
  await assert.rejects(api.login("x@y.test", "bad"), (e: unknown) => e instanceof ApiError && e.message === "invalid credentials");
  assert.equal(fired, 1);
});

test("network failure becomes a friendly ApiError(0)", async () => {
  const { fetchImpl } = mockFetch([new TypeError("fetch failed")]);
  const api = createClient({ fetchImpl, storage: new MemStore() });
  await assert.rejects(api.status(), (e: unknown) => e instanceof ApiError && e.status === 0 && e.code === "network" && /Cannot reach/.test(e.message));
});

test("pydantic 422 lists are flattened; LLM 503 keeps its code; 500 hides details", async () => {
  assert.equal(errorMessage({ detail: [{ loc: ["body", "password"], msg: "String should have at least 10 characters" }] }, 422).message,
    "password: String should have at least 10 characters");
  assert.deepEqual(errorMessage({ detail: "The Groq API key is invalid", code: "llm_unavailable" }, 503), { message: "The Groq API key is invalid", code: "llm_unavailable" });
  assert.match(errorMessage(null, 500).message, /server had a problem/);
  assert.match(errorMessage(null, 429).message, /Too many/);
});

test("file upload sends multipart without forcing a JSON content type", async () => {
  const { fetchImpl, calls } = mockFetch([{ status: 202, body: { job_id: 7 } }]);
  const api = createClient({ fetchImpl, storage: new MemStore() });
  const r = await api.uploadFile(new File(["hello"], "n.txt", { type: "text/plain" }), "Notes", ["eng", "all"]);
  assert.equal(r.job_id, 7);
  const init = calls[0].init;
  assert.ok(init.body instanceof FormData);
  assert.equal((init.body as FormData).get("groups"), "eng,all");
  assert.equal((init.body as FormData).get("title"), "Notes");
  assert.equal((init.headers as Record<string, string>)["Content-Type"], undefined);
});

test("query posts the documented fields", async () => {
  const { fetchImpl, calls } = mockFetch([{ body: { answer: "x" } }]);
  const api = createClient({ fetchImpl, storage: new MemStore() });
  await api.query({ question: "q?", hops: 2, use_graph: false, top_k: 3 });
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body as string), { question: "q?", hops: 2, use_graph: false, top_k: 3 });
});

test("audit passes the action filter encoded", async () => {
  const { fetchImpl, calls } = mockFetch([{ body: [] }]);
  await createClient({ fetchImpl, storage: new MemStore() }).audit(50, "query error");
  assert.equal(calls[0].url, "/audit?limit=50&action=query%20error");
});
