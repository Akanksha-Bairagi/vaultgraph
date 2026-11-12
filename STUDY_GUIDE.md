# Study guide — read in this order, and be able to explain each answer out loud

## 1. Mental model (2 min pitch)
"It's a RAG backend where retrieval and graph traversal respect who's asking. A fast keyword+vector stage finds relevant chunks,
I map them to entities in a knowledge graph, expand a few hops, and give the LLM that connected subgraph so multi-hop questions work
and relationships are preserved. Authorization is enforced in the SQL itself, and I attacked my own system to measure it."

## 2. Module tour (open the file while reading)
| File | What it does | Concept to master |
|---|---|---|
| `db.py` | Tables (orgs, users, groups, documents, doc_acl, chunks, nodes, edges, node_sources, audit_log) + forward-only migration | Normalisation, foreign keys, indexes, schema migration |
| `config.py` | Env config, `.env` loader, production guards | 12-factor config, fail-fast startup, why no default secrets |
| `security.py` | scrypt hashing, JWT | Salting, memory-hard KDF, constant-time compare, pinned `alg` |
| `acl.py` | The single "visible documents" query | Default-deny, RBAC + groups, single source of truth |
| `search.py`, `chunking.py` | BM25, cosine, RRF, sentence-aware chunks | tf-idf intuition, hybrid search, rank fusion |
| `embeddings.py`, `reindex.py` | Hash/BGE embedders, per-chunk embedder name | Never mix vector spaces; graceful fallback |
| `extract.py` | Text -> triples | Entity/relation extraction; validate untrusted output |
| `graph.py` | Nodes/edges, ACL-aware k-hop recursive CTE, overview with provenance | Graph in SQL, provenance-derived visibility |
| `guard.py` | Injection scan + normalisation, output validator | Defence in depth, canary tokens, exfil channels, why regex is never enough |
| `llm.py` | Groq client, error mapping, live model check, simulated vulnerable mock | Provider abstraction, model deprecation, safe error messages |
| `uploads.py` | Upload validation | Allow-lists, magic bytes, resource limits |
| `service.py` | Ingest, retrieve, query, read models for the UI, audit | Orchestration, transactions, authorization in the service layer |
| `api.py` | FastAPI routes, middleware, error handlers, static hosting | Dependency injection, status codes, CSP headers, rate limiting, serving an SPA |
| `frontend/src/lib/api.ts` | Typed fetch client | Error normalisation, 401 handling, testing with injected `fetch` |
| `frontend/src/pages/*` | Screens | Data loading hooks, optimistic UI vs server truth, accessibility basics |
| `frontend/src/lib/forceLayout.ts` | Force-directed graph layout | Simple physics simulation, O(n^2) tradeoffs |
| `eval/run_eval.py` | Recall, leak rate, attack success | Honest evaluation and its limits |

## 3. Trace one request (do this with a debugger)
Browser -> `api.query()` (Bearer token from sessionStorage) -> `POST /query` -> `current_user` (JWT -> user row re-read) -> `service.query` -> `retrieve`: (1) SQL fetch of visible, unflagged chunks
-> (2) BM25 + cosine -> (3) RRF top_k -> (4) seeds = entities in those chunks + names in the question -> (5) `graph.khop` (visible edges only)
-> (6) evidence chunks of those edges join the context -> `build_prompt` (nonce) -> LLM -> `validate_output` -> audit row -> response.

## 4. Interview questions you can now answer
1. **Why enforce ACLs in the query, not the prompt?** Prompts are advisory; a hijacked model ignores them. Data that never enters the context cannot leak.
2. **What's the GraphRAG-specific leak?** Seeds are authorised but expansion follows edges into restricted facts. Fix: edge visibility derives from its evidence document; traversal joins only visible edges/nodes.
3. **Why derive node/edge ACLs from documents?** One source of truth, no drift when a document's groups change.
4. **Why hybrid search + RRF?** BM25 catches exact terms, vectors catch paraphrase; RRF merges ranks without normalising incompatible scores.
5. **When does GraphRAG help?** Multi-hop questions whose answer chunk shares no words with the question; costs extraction + latency.
6. **How do you model a graph in SQL?** Node/edge tables, indexes on src/dst, recursive CTE with a depth bound; `UNION` dedups cycles.
7. **What is indirect prompt injection and what did you do?** Instructions inside retrieved data. Quarantine, normalisation, delimiters, output validation, no tools, ACLs for blast radius. Residual: paraphrase attacks (tested and documented).
8. **A real bug you found?** My first output validator allowed URLs present in the context, but a poisoned chunk supplies its own URL; fixed by always blocking markdown images. Later, improving normalisation closed the letter-spacing gap, so I replaced that test with a paraphrase case instead of deleting the residual-risk test.
9. **How do you know it works?** Regression tests + eval: leaks 8/8 -> 4/8 -> 0/8 across ACL modes; attack success 7/7 -> 1/7 (simulated model; small dataset, say so).
10. **Why bearer token in sessionStorage rather than an HttpOnly cookie?** Cookies resist XSS theft but need CSRF defences and misbehave in third-party iframes (Hugging Face embeds Spaces). I mitigate XSS with React escaping, a strict CSP and short expiry, and document the tradeoff.
11. **Why serve the SPA from FastAPI?** One origin: no CORS, one deployment unit, CSP `connect-src 'self'`. Hash routing avoids path clashes with API routes.
12. **How do you handle LLM provider churn?** Model id from config, live verification against Groq's model list on `/status`, readable errors, offline mock for tests. (Groq retired llama-3.3-70b-versatile in Aug 2026; the default is now `openai/gpt-oss-120b`.)
13. **Production secrets?** `ENV=production` fails fast without a 32+ char `JWT_SECRET`; no default admin; demo accounts only in explicit demo mode.
14. **What would you change at scale?** Postgres + pgvector/FTS (+ row-level security as a second ACL layer), Redis rate limits and a real queue, LLM extraction with schema validation, token revocation, per-tenant encryption, OCR, document deletion with graph cleanup.

## 5. Exercises (build understanding)
- Add a new relation phrase in `extract.py` and a test. - Change `hops` and watch recall/latency. - Remove the `vn` visibility check from `graph.khop` and watch which test fails.
- Swap `HashEmbedder` for BGE and compare recall. - Add a `DELETE /documents/{id}` that removes chunks, edges and orphan nodes.
- Replace SQLite with Postgres (hint: `json_each` -> `jsonb_array_elements_text` or `= ANY(:ids)`).
- Add document deletion (remove chunks, edges, orphan nodes) and a test that the graph shrinks. - Add a Playwright e2e test of login -> upload -> ask. - Swap the rule extractor for an LLM extractor behind the same function with schema validation.
- Re-run the eval with `GROQ_API_KEY` set and compare answer accuracy for plain RAG vs GraphRAG.

## 6. Walk-through script for a demo (3 minutes)
Sign in as **Intern** -> Ask "What is Marcus Lee's salary?" (no answer, nothing leaked) -> sign in as **HR** -> same question (answer with citation) -> as **Ava** open the Graph and select *Platform Team* (no Project Phoenix, no HR edges) ->
as **Admin** open the Audit log and show each person's queries (with sources used) and the quarantined-chunk count -> upload a poisoned text and show it being quarantined.
