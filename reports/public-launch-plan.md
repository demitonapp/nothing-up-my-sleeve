# The public launch plan (13 November 2026)

Justin, 13 November: only he uses the dashboard for the next week (to about 20 November); the site is publicly
accessible in a month (by 13 December); **public site only**: the public edition faces the internet and the dashboard
(4321 and 8787) never does; visitors can connect their own local Ollama or MLX, "our ships too once they're published
on hugging face".

The decisions are S5 proposals (`uv run --project backend thorp proposals list`):

| # | Decision | Phase it gates |
|---|---|---|
| 29 | Access policy: two tiers (public, owner), one Postgres table classifying every address, unclassified = owner | 1 |
| 1 | The public site's data: a static JSON export (recommended) or `thorp dash --public` with an allow-list | 2 |
| 2 | Refuse the two lab writes a public house page can reach | 2 |
| 30 | Ships on Hugging Face: licence for the weights, namespace, first ships | 4 (the upload only) |
| 31 | Where the public site is hosted, and its domain | 3, 5 |

Already built: the login (db6ca537: `thorp login set`, Expeditions and the Liberty Machine gated) and the chat
console's connection to a visitor's local model servers (c6cfc8cd).

## Phase 0 · to 20 November: decisions
Run `thorp login set`. Sign or answer #29, #1, #2, #30, #31.

## Phase 1 · one list of what is public (#29), about 2 to 3 days
- Migration `s5.access`: one row an address (page or API, method), tier `public` or `owner`. Seeded from
  `frontend/src/lib/edition.ts`, `thorp/dash/auth.py` (`GATED`) and the API routes in `thorp/dash/server.py`.
- `server.py` asks the table; an address it does not list is owner-only.
- The public build reads an export of the table (generated, never hand-edited) in place of `edition.ts`.
- The Liberty Machine's check for policy `access`: the built public site links to and calls no owner address.

## Phase 2 · the public site's data (#1, #2), about a week, 23 November to 4 December
- `thorp public export` writes one JSON a public endpoint (about a dozen: leaderboard, labs, lab models, museum, the
  ladder trimmed of local paths and the queue) into the public build; owner fields are left out.
- In the public build the page reads those files, never `/api`; whatever needs a live server is off there (the lab
  downloads, #2). The chat uses only the visitor's own model, as built.
- Proof: build, serve on a `*.localhost` origin, open every page; no request reaches `/api`, none 404s.

## Phase 3 · local Ollama and MLX on the public site, about a day
- The host's Content-Security-Policy `connect-src` allows `http://localhost:*` and `http://127.0.0.1:*`.
- Test Ollama (`OLLAMA_ORIGINS` set to the public origin) and `mlx_lm.server` in Chrome, Firefox and Safari (Safari
  may refuse a secure page's requests to the visitor's machine).

## Phase 4 · our ships on Hugging Face (#30), about 1 to 1.5 weeks, beside phases 1 to 3
1. `thorp publish export <ship>`: a standard Hugging Face folder. The GPT in `thorp/models/gpt_mlx.py` (pre-norm
   LayerNorm without biases, GELU MLP at 4x, tied embeddings, optional grouped KV heads) maps a learned-position ship
   onto GPT-2 (zero biases) and a rotary one onto StarCoder2 (`use_bias` false); the SentencePiece tokeniser with
   byte fallback and the control pieces; a chat ship's template (the tool marks) in `tokenizer_config.json`.
2. Parity: the export's next-token logits match ours within tolerance in `transformers` and `mlx_lm`, or nothing ships.
3. GGUF for Ollama, written by us with the `gguf` package (llama.cpp's converter does not carry a SentencePiece
   vocabulary for those architectures); the same parity through llama.cpp and Ollama.
4. A model card a ship, generated from Postgres: class, books read, scores, licence, limits.
5. `thorp publish push`: Justin logs in to Hugging Face himself; each upload is published, so each waits on his yes.
6. The public console lists "Thorp's ships" with `ollama run hf.co/...` and `mlx_lm.server --model ...`.

## Phase 5 · launch, 8 to 13 December
Hosting and domain (#31), the public build deployed, the phase 2 crawl and the phase 1 check against the live site,
the browser tests, 4321 and 8787 unreachable from outside, the last build kept for rollback.

## Order and risks
Phase 1 before 2 (2's checks read the table); 3 needs only #31; 4 is independent, and only its upload waits on #30.
Biggest risks: the GGUF tokeniser (phase 4) and Safari refusing a public page's requests to localhost (phase 3).
